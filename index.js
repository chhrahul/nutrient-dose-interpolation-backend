require("dotenv").config();
const express = require("express");
const cors = require("cors");
const path = require("path");
const uploadRoute = require("./src/routes/upload");

const app = express();
const PORT = process.env.PORT || 8001;

app.use(cors());
app.use("/output", express.static(path.join(__dirname, "src", "output")));

app.get("/", (req, res) => {
  res.send("✅ Server is running. Use POST /api/upload to upload files.");
});

app.use("/api/upload", uploadRoute);

app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`));

