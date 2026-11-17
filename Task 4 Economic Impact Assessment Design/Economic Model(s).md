# Economic Model Integration Blueprint

Each survey block maps directly to a structural parameter in three econometric and regional economic models, linked spatially via counties\_fips and geo\_ref (seeds\_stakeholder\_pool\_v2.csv) to NAIP/NLCD land-cover layers (county\_landcover\_census.csv, tract\_landcover\_census.csv, blockgroup\_landcover\_census.csv).

## Model A: Spatial Hedonic Pricing Model (HPM)

Purpose: Quantify the capitalization of greenbelt proximity and EO land-cover composition into residential, agricultural, and commercial property values, and estimate municipal property tax revenue gains. (2.4)

Econometric Specification:

$ln({P}_{it})\ =\ {\beta }_{0}+{\beta }_{1}{Dis{t}_{-}Corridor}_{i}+{\beta }_{2}{Dis{t}_{-}Corridor}_{i}^{2}+{X}_{i}^{'}\gamma +{L}_{b}^{'}\delta +{\theta }_{c}+{\tau }_{t}+{\varepsilon }_{it}$

How will the Survey and EO data Fit in:

* Dependent Variable ($ln({P}_{it})$) \- County parcel sales/assessed values (where available) supplemented by 4.3 stated percentage land-value expectations as Bayesian priors or bounds for ex-ante simulation in data-sparse rural counties (e.g., Van Buren, Bledsoe, Grundy).  
* Spatial EO Covariate (${L}_{b}^{'}$) \- Block-group NAIP percentages (naip\_forest\_pct, naip\_wetlands\_pct, naip\_agriculture\_pct, naip\_developed\_pct) and per-capita green space (naip\_forest\_ha\_per\_1000ppl) from blockgroup\_landcover\_census.csv.  
* Land-use transition controls (${X}_{i}^{'}$) \- 4.1 (expected conversion risk vs. easement enrollment) and 4.2 (observed land transactions) interact with ${Dis{t}_{-}Corridor}_{i}$ to separate recreational amenity premiums from speculative subdivision pressure.   
* Fiscal Output: Multiply estimated marginal implicit prices ($\frac{\delta P}{\delta Dist}$) by county millage rates and cross-validate against municipal projections in 2.4.

## Model B: Contingent Valuation Method (CVM) \- Parametric Welfare Estimation

Purpose: Estimate the non-market Total Economic Value (use \+ option \+ existence value) of the greenbelt across counties with different ARC economic distress designations.

Econometric Specification:

$Pr({Yes}_{j}=1)=\frac{1}{1+exp(-[{\alpha }_{0}+{\beta }_{1}{Bid}_{j}+{\beta }_{2}{Distres{s}_{-}Tier}_{c}+{Z}_{j}^{'}\lambda +{L}_{c}^{'}\phi ])}$  
How will the Survey and EO data Fit in:

* Choice & Bid Variables: 5.2 Part A (`Yes/No` to randomized bid `$B`) and Part C (interval/continuous maximum WTP). 5.2 Part B allows you to run sensitivity analyses excluding protest bids vs. treating them as \$0.  
* Attitudinal & Priority Covariates (​${Z}_{j}^{}$): 2.1 (policy priority rankings), 4.4 (ag/environmental trade-off scores), and 5.1 (Quality of Life rating).  
* ARC Economic Status & EO Moderators (${Distres{s}_{-}Tier}_{c}$, ${L}_{c}^{}$): Interact county economic status (e.g., Madison `Competitive` vs. Grundy/Bledsoe `Distressed`) with baseline county forest/agriculture shares (`county_landcover_census.csv`) to test whether residents in heavily forested rural counties (`Marion 79%`, `Grundy 73%`) exhibit diminishing marginal WTP for forest preservation compared to urbanizing counties (`Madison 31.6%` forest, `23.2%` developed).  
* Aggregate Welfare Output: Compute parametric Mean/Median WTP per household (Mean $WTP\ =\ -\frac{{\alpha }_{0}+{Z}_{j}^{'}\lambda +{L}_{c}^{'}\phi }{{\beta }_{1}}$) and aggregate across Census household counts (`U7H001`) by county, establishing the Table 3 baseline for ex-post comparison (Q5.3).

## Model C: Multi-Regional Input-Output (MRIO) and Multiplier Model

Purpose: Quantify the regional economic “Ripple Effects” (Direct, Indirect, and Induced impacts) on GDP per worker, employment, import substitution and tax revenues across the 12 county AL-TN economy. 

Mathematical Framework: $\Delta X={(I-A)}^{-1}\Delta Y$

Where $\Delta Y$ is the vector of final demand shocks and ${(I-A)}^{-1}$ is the Leontief inverse multiplier matrix (calibrated via IMPLAN or BEA RIMS II multipliers for the AL \- TN regional trade area).

How will the Survey and EO data Fit in:

* Capital Expenditure Shock (${\Delta Y}_{CapEx}$​): Derived from 2.2 (agency/funder 5-year capital and maintenance spending commitments) mapped to Construction and Environmental Consulting sectors.  
* Tourism & Recreation Final Demand Shock (${\Delta Y}_{Tourism}$​): Calculated from 3.2 (Baseline Visitors×Expected % Visitation Increase×Average Daily Spend) allocated across 3.1 sectors (Accommodation, Food Services, Retail, Arts/Recreation).  
* Local Sourcing & Import Substitution Adjustment (AA matrix technical coefficients): Responses in 3.3 (local farm-to-restaurant sourcing and cross-county B2B supply chains) and 4.2 (shared local processing/distribution) calibrate the Regional Purchase Coefficients (RPCs), measuring how much visitor spending stays inside the 12 counties rather than leaking out as imports.  
* Workforce & GDP-per-Worker Output: Total output changes ($\Delta X$) are converted into FTE job creation and value-added (GDP) per worker, cross-checked against industry expectations in 3.4.

