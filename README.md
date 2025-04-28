
# Project Name

Nutrient Dose Interpolation

## Description

This is the **Node.js** + **Express** backend for the Nutrient Dose Interpolation Web Application.  
It handles file uploads, runs a Python geostatistical interpolation script (kriging), and returns results as GeoJSON and map images.

## Installation

1. Clone the repository:

    ```bash
       git clone https://github.com/chhrahul/nutrient-dose-interpolation-backend.git
    ```

2. Go to the project directory:

    ```bash
       cd nutrient-dose-interpolation-backend
    ```

3. Install dependencies:

    ```bash
    npm install
    pip install numpy pandas geopandas pykrige matplotlib shapely
    ```

4. Start the server:

    ```bash
    npm start
    ```

## Tech Stack and Version

1. Node -> 23.10.0
2. Express 
2. Python -> 3.13.3

