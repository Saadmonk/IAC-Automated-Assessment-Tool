# ⚡ MALT IAC Report Generator

A Streamlit-based tool for the **MALT Industrial Assessment Center** at the University of Louisiana at Lafayette to generate energy assessment reports after facility visits.

Built for internal use by the MALT IAC team under **Dr. Peng "Solomon" Yin**.

---

## Table of Contents

- [Overview](#overview)
- [Running Locally](#running-locally)
- [Deploying on Streamlit Cloud](#deploying-on-streamlit-cloud)
- [How to Use the Tool](#how-to-use-the-tool)
- [ARC Calculation Methods](#arc-calculation-methods)
- [Saving & Loading Progress](#saving--loading-progress)
- [Project Structure](#project-structure)

---

## Overview

This tool walks your team through every section of a MALT IAC report in order:

1. Enter cover page info (report number, team, facility)
2. Enter 12 months of utility bills → rates are auto-calculated
3. Describe the facility, process, and major equipment
4. Fill in each applicable ARC (Assessment Recommendation) — each page runs the real engineering calculations
5. Review all saved ARs and their totals
6. Generate the full PDF report matching the MALT IAC template

---

## Running Locally

### Requirements
- Python 3.10 or newer — download at [python.org](https://www.python.org/downloads/)

### Setup (one time only)

**1. Download and unzip the project**

Unzip `malt_iac_tool.zip` somewhere on your computer.

**2. Open a terminal in the project folder**

On Windows: open the folder, click the address bar, type `cmd`, press Enter.  
On Mac: right-click the folder → "New Terminal at Folder".

**3. Create a virtual environment**

```bash
python -m venv venv
```

**4. Activate it**

```bash
# Windows:
venv\Scripts\activate

# Mac / Linux:
source venv/bin/activate
```

**5. Install dependencies**

```bash
pip install -r requirements.txt
```

This takes 1–2 minutes. Only needed once.

**6. Run the app**

```bash
streamlit run app.py
```

Your browser will open automatically at `http://localhost:8501`.

### Every time after that

```bash
source venv/bin/activate   # (or venv\Scripts\activate on Windows)
streamlit run app.py
```

---

## Deploying on Streamlit Cloud

Streamlit Community Cloud is **free** and lets your whole team access the tool from any browser without installing anything.

### Step 1 — Upload to GitHub

1. Go to [github.com](https://github.com) and create a new repository (name it anything, e.g. `malt-iac-tool`)
2. Set it to **Private** (recommended for internal tools)
3. On the new repo page, click **"uploading an existing file"**
4. Drag and drop **all files and folders** from inside the `malt_iac_tool` folder into the GitHub uploader:
   - `app.py`
   - `requirements.txt`
   - `packages.txt`
   - `README.md`
   - `pages/` folder
   - `arcs/` folder
   - `utils/` folder
   - `.streamlit/` folder
5. Click **"Commit changes"**

> ⚠️ Make sure `app.py` is at the **root** of the repo, not inside a subfolder.

### Step 2 — Deploy

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account
2. Click **"New app"**
3. Select your repository and set:
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **"Deploy"**

Streamlit will install all packages and give you a URL like:  
`https://your-username-malt-iac-tool.streamlit.app`

Share that link with your team — no installation required on their end.

---

## How to Use the Tool

Work through the pages **in order** using the sidebar navigation.

---

### Page 1 — Cover Info

Fill in:
- Report number (e.g. `LT8438`)
- Site visit date
- Facility location, NAICS/SIC codes, annual sales, employee count
- Principal products
- Team: Lead Faculty (pre-filled as Dr. Yin), Lead Student, Safety Student, others

---

### Page 2 — Utility Billing

Enter **12 months** of utility bills for electricity, gas, and water.

For each month, enter:
- **Electricity:** kWh consumed, energy cost, peak kW demand, demand cost, other fees
- **Gas:** MMBtu consumed, cost, fees
- **Water:** thousand gallons (Tgal), water cost, sewer cost, fees

The tool automatically computes average rates ($/kWh, $/kW, $/MMBtu, $/Tgal) used in all ARC calculations.

Toggle **"Has Gas"** and **"Has Water"** off if the facility doesn't use them.

---

### Page 3 — Facility Background

Fill in:
- **2.1** Facility description (size, construction, type)
- **2.2** Process description (how the facility operates)
- **2.3** Best practices already in place (list up to 5)
- **2.4** Forms of energy: what electricity and gas are used for
- **2.5** Major energy-consuming equipment table (name, specs, quantity, energy form)
- **2.6** Operating schedule (shift hours, days per week)

---

### Page 4 — ARC 2.7221: Thermostat Setback

**Requires smart meter data (CSV file).**

Your CSV needs two columns:
- Daily outdoor air temperature (°F)
- Daily electricity consumption (kWh)

The tool fits all 5 ASHRAE Guideline 14 change-point regression models and selects the best by R²:

| Model | Description |
|-------|-------------|
| 2P | Constant baseline (no weather dependence) |
| 3PC | 3-parameter cooling (linear above balance point) |
| 3PH | 3-parameter heating (linear below balance point) |
| 4P | 4-parameter V-shape (single change point) |
| 5P | 5-parameter (separate heating and cooling slopes) |

Enter the proposed setpoint change (e.g. raise cooling setpoint by 2°F), and savings are calculated using the regression slope × temperature delta × seasonal days.

If no smart meter data is available, use the **Manual Entry** section at the bottom.

---

### Page 5 — ARC 2.7142: LED Lighting Upgrade

Build a fixture inventory table. For each fixture type:
- Description (e.g. "T8 Office Lights")
- Quantity
- Existing lamp type and wattage
- Proposed LED type and wattage
- Annual operating hours (AOH) — leave 0 to use the global default

Savings = (existing W − proposed W) × qty × AOH hours / 1000

---

### Page 6 — ARC 2.2625: Chilled Water Reset

Enter:
- Average cooling load (tons)
- Annual chiller run hours
- Current chilled water supply temperature (CHWST) in °F
- Proposed CHWST after reset (higher = better COP)
- Condenser leaving water temperature

The tool uses the Carnot COP formula scaled by a practical efficiency fraction. COP improvement is converted to kW reduction × run hours = kWh saved.

An optional **CoolProp Loop Verification** section lets you verify loop heat transfer using real fluid properties.

---

### Page 7 — ARC 2.4236: Fix Compressed Air Leaks

Enter each leak location found during the survey:
- Description and quantity
- Either **hole diameter (inches)** — the tool calculates CFM using isentropic orifice flow — or **measured CFM** if you used an ultrasonic detector

System pressure and compressor efficiency are set globally at the top.

---

### Page 8 — ARC 2.4146: VFD on Motors

Enter each motor to receive a VFD:
- Horsepower and motor efficiency (or current kW if known)
- Annual run hours
- Expected speed fraction (e.g. 0.80 = running at 80% of full speed)

Savings use the **cubic affinity law**: P₂/P₁ = (N₂/N₁)³ — a 20% speed reduction = ~49% power reduction.

---

### Page 9 — Other ARCs

Select from 10 additional ARC codes using the dropdown:

| ARC | Title |
|-----|-------|
| 2.7135 | Occupancy Sensors |
| 2.7134 | Photocell Controls |
| 2.6212 | Turn Off Lights When Unoccupied |
| 2.4322 | Energy-Efficient Motors |
| 2.4133 | ECM Motors |
| 2.7447 | Air Curtain / Strip Doors |
| 2.9114 | Solar PV |
| 2.7264 | Interlock HVAC |
| 2.7232 | High-Efficiency HVAC |
| 2.7261 | Timers / Thermostats |

Each uses the appropriate calculation method for that ARC type.

---

### Saving an AR

After calculating savings on any ARC page, click **"Save this AR to Report"**. The AR is stored in the session and will appear in the summary and PDF.

---

### Page 10 — AR Summary

View all saved ARs in one table. You can:
- See totals (combined savings, implementation cost, average payback)
- Reorder ARs (↑ ↓ buttons) — this controls the order they appear in the PDF
- Delete any AR and re-enter it
- Click into any AR to review its observation, recommendation, and calculation details

---

### Page 11 — Executive Summary

Auto-assembled from your billing data and saved ARs. Shows:
- **Section 1.1:** Annual utility usage and cost table
- **Section 1.2:** AR summary table with totals
- Narrative paragraph summarizing the assessment
- Bar chart of savings by AR

Review this page before generating the PDF to catch any errors.

---

### Page 12 — Generate Report

A pre-flight checklist shows any missing fields. Then click **"Generate PDF Report"** to produce and download the full MALT IAC PDF.

The PDF includes:
- Cover page with team info
- Disclaimer and Preface (boilerplate)
- Section 1: Executive Summary (utility table + AR table)
- Section 2: Facility Background (all subsections)
- Section 3: Each AR with observation, recommendation, technology description, and calculation
- Section 4: Cybersecurity (boilerplate)

Running header on every page shows the IAC director name and report number.

---

## ARC Calculation Methods

| ARC | Method |
|-----|--------|
| 2.7221 Thermostat | ASHRAE Guideline 14 change-point regression (5 models), scipy curve_fit |
| 2.7142 LED | ΔW × qty × AOH / 1000 |
| 2.2625 Chilled Water | Carnot COP × cop_fraction, kW = tons×3.517/COP |
| 2.4236 Compressed Air | Isentropic orifice flow (choked), compressor shaft power |
| 2.4146 VFD | Affinity law: P₂ = P₁ × (N₂/N₁)³ |
| 2.7135/2.7134/2.6212 | Total kW × hours saved / 1000 |
| 2.4322/2.4133 Motors | HP × 0.7457 × (1/η₁ − 1/η₂) × hours |
| 2.7232 HVAC EER | tons×12000 × (1/EER₁ − 1/EER₂) / 1000 × hours |
| 2.7264 Interlock | kW_wasted × simultaneous hours |
| 2.7447 Air Curtain | U × A × HDD/CDD × 24 × reduction fraction |
| 2.9114 Solar PV | Area_m² × 1kW/m² × efficiency × peak sun hours |

---

## Saving & Loading Progress

Session data is stored in your browser tab and is lost on refresh. To save your work:

1. Go to **Page 12 — Generate Report**
2. Open the **"Export / Import Session Data"** section
3. Click **"Export Session JSON"** and save the file

To resume later:
1. Upload the JSON file on the same page
2. All your data will reload instantly

---

## Project Structure

```
malt_iac_tool/
├── app.py                          # Main entry point — home dashboard
├── requirements.txt                # Python dependencies
├── packages.txt                    # System packages for Streamlit Cloud
├── README.md                       # This file
├── .streamlit/
│   └── config.toml                 # Theme and server settings
├── pages/
│   ├── 1_Cover_Info.py
│   ├── 2_Utility_Billing.py
│   ├── 3_Facility_Background.py
│   ├── 4_AR_Thermostat.py          # ARC 2.7221
│   ├── 5_AR_LED_Lighting.py        # ARC 2.7142
│   ├── 6_AR_Chilled_Water.py       # ARC 2.2625
│   ├── 7_AR_Compressed_Air.py      # ARC 2.4236
│   ├── 8_AR_VFD.py                 # ARC 2.4146
│   ├── 9_AR_Other.py               # 10 additional ARCs
│   ├── 10_AR_Summary.py
│   ├── 11_Executive_Summary.py
│   └── 12_Generate_Report.py
├── arcs/
│   ├── arc_2_7221_thermostat.py    # ASHRAE GL14 regression engine
│   ├── arc_2_7142_lighting.py      # Lighting savings calculations
│   ├── arc_2_2625_chilled_water.py # CoolProp COP calculations
│   ├── arc_2_4236_compressed_air.py# Orifice flow + compressor power
│   ├── arc_2_4146_vfd.py           # Affinity law calculations
│   └── arc_generic.py              # Motors, HVAC, solar, doors, etc.
└── utils/
    ├── session.py                  # Session state management + rate calc
    └── pdf_generator.py            # ReportLab PDF builder
```

---

## Contact

MALT Industrial Assessment Center  
University of Louisiana at Lafayette  
Director: Dr. Peng "Solomon" Yin  
Funded by the U.S. Department of Energy, Office of Energy Efficiency and Renewable Energy
