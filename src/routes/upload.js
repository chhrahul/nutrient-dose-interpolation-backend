const express = require("express");
const multer = require("multer");
const path = require("path");
const shapefile = require("shapefile");
const xlsx = require("xlsx");
const { execFile } = require("child_process");
const fs = require("fs");

async function convertShpToGeoJSON(shpPath, dbfPath) {
    const geojson = { type: "FeatureCollection", features: [] };

    const source = await shapefile.open(shpPath, dbfPath);
    let result = await source.read();
    while (!result.done) {
        geojson.features.push(result.value);
        result = await source.read();
    }

    return geojson;
}

const router = express.Router();

const uploadPath = path.join(__dirname, "..", "uploads");
if (!fs.existsSync(uploadPath)) fs.mkdirSync(uploadPath, { recursive: true });

const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, uploadPath),
    filename: (req, file, cb) => cb(null, `${Date.now()}-${file.originalname}`),
});
const upload = multer({ storage });

router.post(
    "/",
    upload.fields([
        { name: "plotFiles", maxCount: 2 }, // .shp + .dbf
        { name: "sampleFile", maxCount: 1 }
    ]),
    async (req, res) => {
        const plotFiles = req.files.plotFiles;
        const sampleFile = req.files.sampleFile?.[0];

        if (!plotFiles || plotFiles.length < 1 || !sampleFile) {
            return res.status(400).json({ error: "Files not received properly. Please upload both a plot file and a sample file." });
        }

        let geojson;
        let plotPath = "";

        // Handle GeoJSON directly
        const geojsonFile = plotFiles.find(f => f.originalname.endsWith(".geojson"));
        if (geojsonFile) {
            geojson = JSON.parse(fs.readFileSync(geojsonFile.path, "utf8"));
            plotPath = geojsonFile.path;
        } else {
            const shpFile = plotFiles.find(f => f.originalname.endsWith(".shp"));
            const dbfFile = plotFiles.find(f => f.originalname.endsWith(".dbf"));

            if (!shpFile || !dbfFile) {
                return res.status(400).json({ error: "Both .shp and .dbf files are required." });
            }

            try {
                geojson = await convertShpToGeoJSON(shpFile.path, dbfFile.path);
                plotPath = shpFile.path.replace(".shp", ".geojson");
                fs.writeFileSync(plotPath, JSON.stringify(geojson));
            } catch (e) {
                return res.status(500).json({ error: "Failed to convert SHP to GeoJSON.", details: e.message });
            }
        }

        const getBoundsFromGeoJSON = (geojson) => {
            let coords = [];
            geojson.features.forEach((feature) => {
                const geometry = feature.geometry;
                if (geometry.type === "Polygon") {
                    coords.push(...geometry.coordinates[0]);
                } else if (geometry.type === "MultiPolygon") {
                    geometry.coordinates.forEach((poly) => coords.push(...poly[0]));
                }
            });
            const lats = coords.map((c) => c[1]);
            const lngs = coords.map((c) => c[0]);
            return [
                [Math.min(...lats), Math.min(...lngs)],
                [Math.max(...lats), Math.max(...lngs)],
            ];
        };

        const bounds = getBoundsFromGeoJSON(geojson);

        const samplePath = sampleFile.path;
        if (sampleFile.originalname.endsWith(".xlsx")) {
            const wb = xlsx.readFile(samplePath);
            const ws = wb.Sheets[wb.SheetNames[0]];
            const csvData = xlsx.utils.sheet_to_csv(ws);
            fs.writeFileSync(samplePath.replace(".xlsx", ".csv"), csvData);
        }

        const sampleCsvPath = samplePath.endsWith(".xlsx")
            ? samplePath.replace(".xlsx", ".csv")
            : samplePath;

        const outputImage = `output_${Date.now()}.svg`;
        const outputPath = path.join(__dirname, "..", "output", outputImage);
        const scriptPath = path.join(__dirname, "..", "scripts", "interpolate.py");
        const pythonExecutable = path.join(__dirname, "..", "..", "venv", "bin", "python3");

        execFile(
            pythonExecutable,
            [scriptPath, plotPath, sampleCsvPath, outputPath],
            (err, stdout, stderr) => {
                if (err) {
                    const errorMessage = stderr?.toString() || err.message || "Unknown error during interpolation";
                    return res.status(500).json({ error: errorMessage });
                }

                const match = stdout.toString().match(/BOUNDS_JSON:([\[\]0-9.,\s]+)/);
                const bounds = match ? JSON.parse(match[1]) : [[0, 0], [100, 100]];

                const warnings = stdout
                    .toString()
                    .split('\n')
                    .filter(line => line.startsWith('WARNING:'))
                    .map(line => line.replace('WARNING:', '').trim());

                const overlayUrl = `http://localhost:${process.env.PORT || 8000}/output/${outputImage}`;
                return res.json({ overlayUrl, bounds, geojson, warnings });
            }
        );

    }
);

module.exports = router;



