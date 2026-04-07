"""
Default observation, recommendation, and technology description text for each ARC.
Energy assessors can edit these in-app; these are the starting templates.
Sources: DOE IAC Best Practices, ASHRAE, Compressed Air Challenge, NREL.
"""

ARC_DEFAULTS = {
    "2.7221": {
        "title": "Thermostat Setback / Setpoint Optimization",
        "observation": (
            "During the site visit, thermostat setpoints were found to remain constant at "
            "{cooling_sp}°F cooling / {heating_sp}°F heating 24 hours a day, 7 days a week, "
            "including nights, weekends, and holidays when the facility is unoccupied. "
            "Smart meter data indicates a strong correlation between outdoor air temperature "
            "and daily electricity consumption, confirming that HVAC is the dominant energy load."
        ),
        "recommendation": (
            "Install programmable or smart thermostats and implement a setback schedule: "
            "raise the cooling setpoint to {cooling_sp_prop}°F and lower the heating setpoint "
            "to {heating_sp_prop}°F during unoccupied hours (nights, weekends). "
            "This will reduce HVAC energy consumption without impacting occupant comfort "
            "during operating hours. Estimated annual electricity savings are {ann_kwh:,.0f} kWh "
            "at a cost savings of ${ann_cost:,.0f}/yr with a simple payback of {payback:.1f} years."
        ),
        "tech_description": (
            "A thermostat setback strategy adjusts HVAC setpoints during unoccupied periods to "
            "reduce conditioning loads. ASHRAE Guideline 14-2014 change-point regression models "
            "are used to establish the relationship between outdoor air temperature and daily "
            "energy consumption. The best-fit model is selected from five candidates (2P, 3PC, "
            "3PH, 4P, 5P) based on coefficient of determination (R²) and CV(RMSE). Savings are "
            "estimated as: ΔE = b₁ × ΔT × N_seasonal_days, where b₁ is the regression slope "
            "(kWh/°F/day) and ΔT is the proposed setpoint adjustment."
        ),
    },

    "2.7142": {
        "title": "Upgrade to LED Lighting",
        "observation": (
            "The facility currently uses {existing_lamp_type} lighting throughout the "
            "{area_description}. The existing fixtures consume {existing_watts}W each and "
            "operate approximately {aoh:,.0f} hours per year. Lighting accounts for an "
            "estimated {pct_lighting:.0f}% of total electricity consumption. "
            "Several fixtures were observed to be aging, with visible lumen depreciation "
            "and some ballast failures noted."
        ),
        "recommendation": (
            "Replace all {existing_lamp_type} fixtures with equivalent LED lamps. "
            "LED replacements for this application consume {proposed_watts}W per fixture — "
            "a {pct_reduction:.0f}% reduction in lighting power. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr) with a "
            "simple payback of {payback:.1f} years. LED fixtures also offer 50,000+ hour "
            "rated lifetimes, significantly reducing lamp replacement and maintenance costs."
        ),
        "tech_description": (
            "LED (Light Emitting Diode) technology produces light through solid-state "
            "electroluminescence, achieving efficacies of 100–150 lm/W compared to 70–95 lm/W "
            "for fluorescent T8 lamps and 15 lm/W for incandescent sources. Modern LED "
            "replacements maintain lumen output over their full rated life (L70 ≥ 50,000 hours), "
            "eliminating the frequent relamping cycles associated with fluorescent and HID sources. "
            "Annual energy savings are calculated as: ΔkWh = (W_existing − W_LED) × N_fixtures × "
            "AOH / 1000, where AOH is annual operating hours."
        ),
    },

    "2.2625": {
        "title": "Chilled Water Supply Temperature Reset",
        "observation": (
            "The chilled water supply temperature (CHWST) is maintained at a fixed setpoint "
            "of {chwst_current}°F year-round, regardless of outdoor conditions or actual "
            "cooling load. During mild weather and partial-load conditions, the chiller "
            "operates at significantly lower efficiency than necessary to maintain this "
            "conservative setpoint. The chiller serves approximately {cooling_tons} tons "
            "of connected cooling load and operates {run_hours:,.0f} hours per year."
        ),
        "recommendation": (
            "Implement a chilled water reset (CHWST reset) control strategy that raises the "
            "supply temperature setpoint to {chwst_proposed}°F during periods of reduced "
            "cooling demand or mild outdoor conditions. This reset can be implemented as "
            "an outdoor air temperature (OAT) reset or a load-based reset through the "
            "existing Building Automation System (BAS). Estimated annual savings: "
            "{ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr) with a simple payback of {payback:.1f} years."
        ),
        "tech_description": (
            "Chilled water supply temperature reset raises the CHWST setpoint when full "
            "cooling capacity is not required, improving chiller coefficient of performance (COP). "
            "The COP improvement is estimated using the Carnot COP formula: "
            "COP = η × T_evap / (T_cond − T_evap), where T_evap and T_cond are evaporator and "
            "condenser temperatures in Kelvin, and η is the practical efficiency fraction "
            "(typically 0.55–0.65 for centrifugal chillers). A 1°F increase in CHWST typically "
            "yields a 1.5–2% improvement in chiller efficiency. Annual kWh savings = "
            "ΔkW × operating hours, where ΔkW = Q_cooling × (1/COP_current − 1/COP_proposed)."
        ),
    },

    "2.4236": {
        "title": "Fix Compressed Air Leaks",
        "observation": (
            "An ultrasonic leak survey of the compressed air system was conducted during "
            "the site visit. A total of {n_leaks} leaks were identified throughout the "
            "distribution system, primarily at fittings, quick-disconnect couplers, "
            "hose connections, and control valve packing. The system operates at "
            "{pressure_psig} psig with the compressor running approximately {run_hours:,.0f} "
            "hours per year. Total estimated leak flow is {total_cfm:.1f} CFM, representing "
            "approximately {pct_leak:.0f}% of system capacity."
        ),
        "recommendation": (
            "Repair all identified compressed air leaks immediately using appropriate "
            "fittings, thread sealant, or hose replacements. Implement a quarterly "
            "ultrasonic leak detection program to identify and repair new leaks before "
            "they accumulate. Tag and log all repairs. Estimated annual savings from "
            "eliminating the identified leaks: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr) "
            "with a simple payback of {payback:.1f} years."
        ),
        "tech_description": (
            "Compressed air leaks are one of the most significant sources of energy waste "
            "in industrial facilities, typically accounting for 20–30% of compressor output "
            "in poorly maintained systems. Leak flow rate is estimated using isentropic "
            "orifice flow theory for choked conditions (system pressure > ~30 psig): "
            "Q = 0.7854 × D² × Cd × P_abs/14.696 [CFM], where D is equivalent orifice "
            "diameter (inches), Cd is the discharge coefficient (≈0.65), and P_abs is "
            "absolute supply pressure (psia). Compressor shaft power required to supply "
            "the leaked air is calculated from isentropic compression work and converted "
            "to electrical input power using compressor and motor efficiencies."
        ),
    },

    "2.4239": {
        "title": "Reduce Compressed Air System Pressure",
        "observation": (
            "The compressed air system is currently operated at {pressure_current} psig. "
            "A review of connected equipment nameplates and process requirements indicates "
            "that the actual minimum required pressure is {pressure_min} psig. "
            "The excess system pressure represents unnecessary compressor work. "
            "For every 2 psig reduction in discharge pressure, compressor power "
            "decreases by approximately 1%."
        ),
        "recommendation": (
            "Reduce the compressor discharge pressure setpoint from {pressure_current} psig "
            "to {pressure_proposed} psig — the minimum required to satisfy all end uses "
            "with an appropriate safety margin. Verify that all equipment operates "
            "satisfactorily at the reduced pressure before permanent implementation. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr)."
        ),
        "tech_description": (
            "Compressor power scales approximately linearly with pressure ratio. "
            "The power reduction from a pressure decrease is estimated using the "
            "polytropic compression formula: ΔP_ratio = (P2_new/P1)^((k-1)/k) / "
            "(P2_old/P1)^((k-1)/k), where k = 1.4 for air. A rule of thumb is "
            "~0.5% power reduction per 1 psig reduction in discharge pressure. "
            "MEASUR Pressure Reduction calculator methodology is applied."
        ),
    },

    "2.4146": {
        "title": "Install Variable Frequency Drive (VFD) on Motor",
        "observation": (
            "The {equipment_description} is driven by a {hp}-HP motor operating at "
            "fixed speed via throttling control (dampers/valves) to regulate flow. "
            "The motor runs approximately {run_hours:,.0f} hours per year and the "
            "average required flow is estimated at {speed_pct:.0f}% of design capacity. "
            "Throttling wastes energy that could be recovered by reducing motor speed."
        ),
        "recommendation": (
            "Install a Variable Frequency Drive (VFD) on the {equipment_description} motor "
            "to directly control flow by varying motor speed, eliminating throttling losses. "
            "Remove or fully open the existing flow control device after VFD installation. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr) with a "
            "simple payback of {payback:.1f} years."
        ),
        "tech_description": (
            "Variable Frequency Drives control motor speed by varying the frequency of the "
            "electrical supply. Per the affinity laws for centrifugal machines: flow ∝ speed, "
            "pressure ∝ speed², and power ∝ speed³. A 20% reduction in speed results in "
            "approximately 49% reduction in power consumption. Annual savings = "
            "(P_full × [1 − (N_reduced/N_full)³]) × operating hours, where N_reduced/N_full "
            "is the average speed fraction at reduced flow."
        ),
    },

    "2.7135": {
        "title": "Install Occupancy Sensors for Lighting Control",
        "observation": (
            "Lighting in {area_description} was observed to remain ON during periods of "
            "inactivity, including during lunch breaks, after production shifts, and on "
            "weekends. The area is occupied for approximately {occ_hours:,.0f} hours per "
            "year but lights currently operate for an estimated {current_hours:,.0f} hours "
            "per year. Total connected lighting load in uncontrolled areas is {total_kw:.1f} kW."
        ),
        "recommendation": (
            "Install occupancy sensors (passive infrared or ultrasonic) in {area_description} "
            "to automatically turn off lights when the space is unoccupied. "
            "Sensors should be set with a time delay of 10–15 minutes to avoid nuisance "
            "switching. Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr) "
            "with a simple payback of {payback:.1f} years."
        ),
        "tech_description": (
            "Occupancy sensors detect human presence using passive infrared (PIR), ultrasonic, "
            "or dual-technology detection. When no occupancy is detected for the programmed "
            "time delay, lights are switched off automatically. Energy savings = "
            "P_lighting (kW) × annual unoccupied hours × occupancy sensor effectiveness factor "
            "(typically 0.8–0.95 depending on space type and sensor coverage)."
        ),
    },

    "2.7134": {
        "title": "Install Photocell Controls for Exterior Lighting",
        "observation": (
            "Exterior lighting at the facility operates on a fixed timer schedule. "
            "During the site visit, exterior lights were observed to remain ON during "
            "daylight hours on overcast days, and the timer schedule did not account "
            "for seasonal variation in sunrise/sunset times. Total exterior lighting "
            "load is approximately {total_kw:.1f} kW."
        ),
        "recommendation": (
            "Replace fixed-time controls with photocell (daylight sensor) controls for "
            "all exterior lighting. Photocells automatically turn lights ON at dusk and "
            "OFF at dawn, eliminating wasted energy during daylight hours and adjusting "
            "automatically for seasonal variation. Estimated annual savings: "
            "{ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr)."
        ),
        "tech_description": (
            "Photocell controls use a photoelectric sensor to detect ambient light levels "
            "and switch lighting accordingly. Compared to a fixed 12-hour timer, photocell "
            "control typically reduces exterior lighting operating hours by 10–20% annually "
            "due to seasonal variation in day length. Savings = P_exterior (kW) × "
            "hours_saved_per_year."
        ),
    },

    "2.6212": {
        "title": "Turn Off Lights in Unoccupied Areas",
        "observation": (
            "Lights in {area_description} were found to be consistently left on during "
            "non-production hours (nights and weekends). These areas are unoccupied for "
            "approximately {unoccupied_hrs:,.0f} hours per year. The connected lighting "
            "load in these areas is {total_kw:.1f} kW."
        ),
        "recommendation": (
            "Implement a policy requiring lights to be turned off when {area_description} "
            "is not in use. Consider installing occupancy sensors (ARC 2.7135) as an "
            "automated solution. As a minimum, designate a 'last person out' responsibility "
            "for each area. Post reminder signage at light switches. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr)."
        ),
        "tech_description": (
            "This recommendation addresses behavioral and operational practices for lighting "
            "energy management. Energy savings are calculated as: "
            "ΔkWh = P_lighting (kW) × unoccupied hours per year. "
            "This is the simplest and lowest-cost lighting energy conservation measure, "
            "requiring no capital investment beyond signage and training."
        ),
    },

    "2.4322": {
        "title": "Replace with Energy-Efficient Motors",
        "observation": (
            "The {motor_description} motor (nameplate {hp} HP) was identified as a "
            "standard-efficiency motor with a nameplate efficiency of {eff_existing:.1%}. "
            "The motor operates approximately {run_hours:,.0f} hours per year at or near "
            "full load. Premium efficiency motors for this frame size achieve "
            "{eff_proposed:.1%} efficiency per NEMA MG-1 Table 12-12."
        ),
        "recommendation": (
            "At next scheduled motor replacement or failure, install a NEMA Premium® "
            "efficiency motor in place of the existing standard efficiency unit. "
            "Do not rewind the existing motor if it fails — rewinding typically reduces "
            "efficiency by 1–2 percentage points. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr) with a "
            "simple payback of {payback:.1f} years."
        ),
        "tech_description": (
            "NEMA Premium® efficiency motors meet or exceed the efficiency levels defined "
            "in NEMA MG-1 Table 12-12, which are 2–8% higher than standard efficiency motors "
            "depending on horsepower rating. Annual kWh savings = HP × 0.7457 × "
            "(1/η_standard − 1/η_premium) × operating hours, where η is full-load efficiency."
        ),
    },

    "2.4133": {
        "title": "Install Electronically Commutated Motors (ECM)",
        "observation": (
            "The {equipment_description} uses a {hp}-HP permanent split capacitor (PSC) "
            "or shaded pole motor operating at fixed speed. ECM (Electronically Commutated "
            "Motor) technology offers significantly higher part-load efficiency for "
            "variable-load applications such as fans and blowers."
        ),
        "recommendation": (
            "Replace the existing PSC/shaded pole motor with an ECM motor. "
            "ECMs offer 20–30% efficiency improvement at full load and even greater "
            "savings at part load due to their brushless DC design. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr)."
        ),
        "tech_description": (
            "Electronically Commutated Motors use a permanent magnet rotor and electronic "
            "commutation, achieving full-load efficiencies of 70–80% compared to 30–60% "
            "for PSC motors. At part load (50%), ECMs maintain 60–70% efficiency while "
            "PSC efficiency drops to 20–40%. Savings = HP × 0.7457 × "
            "(1/η_PSC − 1/η_ECM) × operating hours."
        ),
    },

    "2.7447": {
        "title": "Install Air Curtains or Strip Doors at Loading Dock",
        "observation": (
            "The loading dock door(s) at this facility remain open for extended periods "
            "during loading/unloading operations, allowing unconditioned outdoor air to "
            "infiltrate the building. The door(s) are approximately {width}×{height} ft "
            "and open for an estimated {open_hrs:,.0f} hours per year. "
            "Given the facility's location, this creates significant heating and cooling loads."
        ),
        "recommendation": (
            "Install high-velocity air curtains above the loading dock door openings, "
            "or install PVC strip doors as a lower-cost alternative. Air curtains create "
            "an invisible barrier of high-velocity air that blocks infiltration while "
            "allowing unimpeded forklift and personnel access. "
            "Estimated annual savings: {ann_cost:,.0f}/yr (electricity + gas combined)."
        ),
        "tech_description": (
            "Air infiltration energy loss is estimated using the degree-day method: "
            "Q_heating = U × A × HDD × 24 × reduction_fraction [BTU/yr], and similarly "
            "for cooling. The U-value for an open door opening is approximately 0.5 "
            "BTU/hr·ft²·°F (equivalent to a 2 mph wind through the opening). "
            "Air curtains typically achieve 80% reduction in infiltration when properly "
            "sized and installed per manufacturer guidelines."
        ),
    },

    "2.9114": {
        "title": "Install Rooftop Solar Photovoltaic System",
        "observation": (
            "The facility has approximately {roof_area:,.0f} sq ft of south-facing "
            "unobstructed roof area suitable for photovoltaic installation. "
            "The facility is located at {location} (latitude {lat:.2f}°), "
            "which receives an annual average of {psh:.1f} peak sun hours per day "
            "per NREL PVWatts data. The facility currently purchases all electricity "
            "from the grid at ${elec_rate:.4f}/kWh."
        ),
        "recommendation": (
            "Install a {rated_kw:.1f} kW rooftop PV system on the available roof area. "
            "The system is estimated to generate {ann_kwh:,.0f} kWh annually, offsetting "
            "approximately {pct_offset:.1f}% of current electricity consumption. "
            "Estimated annual cost savings: ${ann_cost:,.0f}/yr with a simple payback "
            "of {payback:.1f} years (before incentives). Federal ITC (30%) may apply."
        ),
        "tech_description": (
            "Photovoltaic (PV) systems convert sunlight directly into electricity using "
            "semiconductor cells. Annual energy production is estimated using NREL's "
            "PVWatts® model (v8), which uses TMY (Typical Meteorological Year) weather data "
            "for the site location and accounts for system losses including soiling, "
            "wiring, inverter efficiency, and shading. System losses are assumed at "
            "{losses:.1f}% per PVWatts defaults. DC-to-AC ratio = {dc_ac_ratio}. "
            "Tilt = {tilt}°, Azimuth = {azimuth}° (south-facing)."
        ),
    },

    "2.7264": {
        "title": "Interlock HVAC to Prevent Simultaneous Heating and Cooling",
        "observation": (
            "During the site visit, it was observed that heating and cooling systems "
            "in {area_description} operate simultaneously during certain periods — "
            "one system conditioning the space while the other works against it. "
            "This typically occurs in shoulder seasons when perimeter heating and "
            "interior cooling operate concurrently. Estimated overlap: "
            "{sim_hours:,.0f} hours/year at {overlap_tons:.1f} tons of wasted cooling."
        ),
        "recommendation": (
            "Program the Building Automation System (BAS) or install interlocking controls "
            "to prevent simultaneous heating and cooling in the same zone. Implement a "
            "dead band of at least 4°F between heating and cooling setpoints. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr)."
        ),
        "tech_description": (
            "Simultaneous heating and cooling occurs when HVAC controls lack proper "
            "dead-band control or when system zoning is inadequate. Energy wasted = "
            "kW_cooling × simultaneous_hours + additional heating energy to offset "
            "overcooling. kW_cooling = tons × 3.517 / EER. This waste is eliminated "
            "entirely by proper controls interlock programming — a no-cost or low-cost measure."
        ),
    },

    "2.7232": {
        "title": "Replace with High-Efficiency HVAC Equipment",
        "observation": (
            "The {equipment_description} ({tons}-ton unit, installed {install_year}) "
            "has a rated EER/SEER of {eer_existing}. This unit is {age} years old and "
            "approaching end of useful life. Current minimum efficiency standards require "
            "EER ≥ {min_eer} for this equipment class. High-efficiency replacements "
            "achieve EER of {eer_proposed}."
        ),
        "recommendation": (
            "At next scheduled replacement, specify a high-efficiency unit with EER ≥ "
            "{eer_proposed} (or SEER2 ≥ equivalent). Request energy efficiency rebates "
            "from the utility before purchasing. "
            "Estimated incremental annual savings vs. minimum code unit: "
            "{ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr)."
        ),
        "tech_description": (
            "HVAC equipment efficiency is rated by EER (Energy Efficiency Ratio, BTU/Wh) "
            "for cooling and COP for heating. Annual kWh savings = tons × 12,000 × "
            "(1/EER_existing − 1/EER_proposed) / 1,000 × run hours. "
            "High-efficiency equipment typically costs 15–30% more than minimum code "
            "equipment but provides energy savings throughout its 15–20 year service life."
        ),
    },

    "2.7261": {
        "title": "Install Timers / Programmable Controls",
        "observation": (
            "{equipment_description} operates continuously without time-based controls, "
            "including during non-production hours. The equipment has a connected load "
            "of {total_kw:.1f} kW and currently operates an estimated {current_hrs:,.0f} "
            "hours per year. Production hours are {prod_hrs:,.0f} hours per year, "
            "suggesting {idle_hrs:,.0f} hours of unnecessary operation annually."
        ),
        "recommendation": (
            "Install programmable timers or connect to the facility BAS to automatically "
            "turn off {equipment_description} during non-production hours. Set up a "
            "schedule matching the facility operating hours. "
            "Estimated annual savings: {ann_kwh:,.0f} kWh (${ann_cost:,.0f}/yr)."
        ),
        "tech_description": (
            "Programmable timers and BAS scheduling controls are among the lowest-cost "
            "energy conservation measures available. Savings = P_equipment (kW) × "
            "idle hours per year. Simple 7-day programmable timers cost $20–$100 and "
            "can be installed without an electrician in many applications."
        ),
    },
}


def get_defaults(arc_code: str) -> dict:
    """Return default text dict for an ARC code. Strips '.' to normalize keys."""
    # Normalize: accept '2.7142' or '2_7142'
    code = arc_code.replace("_", ".").strip()
    return ARC_DEFAULTS.get(code, {
        "title": f"ARC {code}",
        "observation": "",
        "recommendation": "",
        "tech_description": "",
    })
