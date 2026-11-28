# Rider profile sources

Where every number in the four profiles comes from. Status: **M** = measured
(taken directly from a source), **D** = derived (calculated from sourced
numbers), **A** = assumed (no source found).

## How the profiles were built

Valenzuela et al. (2022) is the backbone for the men: body mass by rider type
(Table 3) and power-duration percentiles for 144 professionals (Table 1).
Their power data by rider type exist only as plots (Fig. 3), so each type is
mapped to a percentile row. Time trialists had the highest *absolute* power,
so they get the 75th-percentile absolute row. Climbers had the lowest absolute
but higher *relative* power, so they get the median relative row times their
mass. Both mappings reproduce the type-specific CP that Horvath & Andersson
(2025) derived from the same dataset to within about 1%, which is the main
check on them. The women's numbers follow the same recipe with Mateo-March et
al. (2022); per-type women's masses and positions are not published, so they
are scaled from the men's type differences.

## Provenance

| Profile | Parameter | Value | Status | Source | Note |
| --- | --- | --- | --- | --- | --- |
| tt_specialist | rider mass | 72.6 kg | M | Valenzuela 2022, Table 3 | Time-trial specialists, n = 11, 72.6 ± 5.4 kg |
| tt_specialist | bike mass | 8.5 kg | A | – | TT bike with disc and deep front wheel; UCI minimum 6.8 kg |
| tt_specialist | $C_dA$ | 0.211 m² | M | Defraeye 2010 | Wind tunnel, time-trial position |
| tt_specialist | $C_{rr}$ | 0.0032 | M | Martin 1998 (citing Kyle 1988) | Mean of 10 high-pressure clinchers on smooth asphalt (0.0027–0.0040) |
| tt_specialist | LT2 ($CP_0$) | 412 W | D | Valenzuela 2022, Table 1, p75 absolute | Fit through the stamina model at 5/10/20 min (see below). The plain linear fit gives 400 W; cross-check: Horvath & Andersson 2025, 395.3 W |
| tt_specialist | LT1 | 309 W | A | – | 75% of LT2 |
| tt_specialist | W′ | 28.75 kJ | D | same fit | The plain linear fit gives 31.8 kJ |
| tt_specialist | $P_\text{max}$ | 1306 W | D | Valenzuela 2022, 5 s p50 relative (17.99 W/kg) × 72.6 kg | |
| climber | rider mass | 63.2 kg | M | Valenzuela 2022, Table 3 | Climbers, n = 50, 63.2 ± 4.4 kg |
| climber | bike mass | 7.5 kg | A | – | Lighter TT setup for hilly courses |
| climber | $C_dA$ | 0.217 m² | D | Garcia-Lopez 2014 (0.237 m²) × frontal-area ratio | Frontal area 0.185 × body surface area (Padilla 1999), Du Bois formula |
| climber | LT2 ($CP_0$) | 370 W | D | Valenzuela 2022, Table 1, p50 relative (7.06/6.45/6.03 W/kg) × 63.2 kg | Fit through the stamina model. Plain linear fit: 359 W; cross-check: Horvath & Andersson 2025, 354.1 W |
| climber | LT1 | 278 W | A | – | 75% of LT2 |
| climber | W′ | 24.1 kJ | D | same fit | Plain linear fit: 27.5 kJ |
| climber | $P_\text{max}$ | 1137 W | D | 17.99 W/kg × 63.2 kg | |
| tt_specialist_women | rider mass | 61.7 kg | D | Ebert 2005 (57.9 kg, n = 15) × men's TT / average mass ratio (1.066) | |
| tt_specialist_women | $C_dA$ | 0.188 m² | D | 0.211 m² × frontal-area ratio | Height 172.4 cm, scaled from Ebert 2005 |
| tt_specialist_women | LT2 ($CP_0$) | 307 W | D | Mateo-March 2022, P75 at 5/10/20 min (6.3/5.6/5.2 W/kg) × 61.7 kg | Fit through the stamina model. Plain linear fit: 298 W |
| tt_specialist_women | LT1 | 230 W | A | – | 75% of LT2 |
| tt_specialist_women | W′ | 25.7 kJ | D | same fit | Plain linear fit: 27.8 kJ |
| tt_specialist_women | $P_\text{max}$ | 944 W | D | Mateo-March 2022, 5 s mean 15.3 W/kg × 61.7 kg | |
| climber_women | rider mass | 53.7 kg | D | 57.9 kg × men's climber / average mass ratio (0.928) | |
| climber_women | $C_dA$ | 0.193 m² | D | 0.237 m² × frontal-area ratio | Height 165.8 cm |
| climber_women | LT2 ($CP_0$) | 261 W | D | Mateo-March 2022, P50 × 53.7 kg | Fit through the stamina model to the 5/10/20 min powers implied by the plain fit (255 W, 16.1 kJ). 4.86 W/kg, below the women's specialist (see below) |
| climber_women | LT1 | 196 W | A | – | 75% of LT2 |
| climber_women | W′ | 14.9 kJ | D | same fit | Plain linear fit: 16.1 kJ |
| all | $\gamma$, $\tau_F$ | 1.7, 3000 s | D | Clark 2019, Mateo-March 2024 | Population values, not per rider; see [../power_model/README.md](../power_model/README.md) and [../SOURCES.md](../SOURCES.md) |
| all | $E_W$ | 57.4 kJ per kg of body mass | D | Clark 2019 | Same |
| climber_women | $P_\text{max}$ | 822 W | D | 15.3 W/kg × 53.7 kg | |

All profiles use $C_{rr}$ = 0.0032 (Martin 1998). The women's bike masses
match the men's (assumed). The men's average used in the ratios (68.09 kg,
180.1 cm) is the n-weighted mean over all five rider types in Valenzuela
Table 3.

## CP and W′ fits

**Step 1, the plain fit.** W = CP·t + W′, least squares at t = 300, 600 and
1200 s; every R² > 0.999. The 3-minute value is not in either source's
tables, so the fit uses 5–20 min only.

| Profile | Input rows | P at 5/10/20 min (W) | CP (W) | W′ (J) |
| --- | --- | --- | --- | --- |
| tt_specialist | Valenzuela Table 1, p75 absolute | 503 / 455 / 426 | 399.9 | 31,800 |
| climber | Valenzuela Table 1, p50 relative × 63.2 kg | 446.2 / 407.6 / 381.1 | 358.7 | 27,492 |
| tt_specialist_women | Mateo-March P75 × 61.7 kg | 388.7 / 345.5 / 320.8 | 297.9 | 27,765 |
| climber_women | Mateo-March P50 × 53.7 kg | – | 255 | 16,100 |

**Step 2, the fit through the stamina model.** The plain fit assumes that
critical power stays fixed during an effort. The stamina model has it sink
as fatigue builds, so using the plain-fit CP as the fresh critical power
would count that fatigue twice. `power_model/calibrate.py` therefore fits
LT2 and W′ so that the model's own power-duration curve passes through the
same 5/10/20 min powers, with LT1 held at 75% of LT2 and $\gamma$, $\tau_F$,
$E_W$ at their population values. These are the values in the profiles.
Each profile stores the three powers it was fitted to as `best_efforts`.

| Profile | LT2 (W) | LT1 (W) | W′ (J) | Model minus data at 5/10/20 min (W) |
| --- | --- | --- | --- | --- |
| tt_specialist | 412 | 309 | 28,750 | +0.2 / −0.9 / +0.4 |
| climber | 370 | 278 | 24,100 | +0.3 / −2.4 / +0.7 |
| tt_specialist_women | 307 | 230 | 25,710 | −0.3 / −0.7 / −0.3 |
| climber_women | 261 | 196 | 14,890 | −0.2 / +1.1 / −0.3 |

## Choices and open points

1. **Women's climber follows the data.** Mateo-March et al. (2022) found that
   women's time trialists had higher relative power than climbers over
   10–60 min, and Impellizzeri et al. (2008) found them about equal once
   normalised by mass. So the women's climber uses the P50 row and ends up
   slightly below the specialist in W/kg. This is a finding to report, not
   an error.
2. **Time trialists' $C_dA$.** 0.211 m² is the wind-tunnel time-trial value
   reported by Defraeye et al. (2010). The climbers keep the frontal-area
   scaling of the Garcia-Lopez (2014) professional value, which represents
   a less optimised position. *To check:* the 0.211 m² value and the test
   rider against the full text.
3. **Women's percentile table.** The P10–P90 values are a secondary
   reproduction attributed to Mateo-March 2022; its men's table matches
   Valenzuela Table 1 exactly and its women's P50 values match the paper's
   abstract. *To check* against the paper itself.
4. **W′ depends on the method.** The linear fits give 16–32 kJ. Horvath &
   Andersson report 18–23 kJ from a 3-parameter model whose W′ is a different
   quantity. The linear 2-parameter fit is the one that matches the W′-balance
   model used here. Best-ever efforts from different days tend to inflate W′.
5. **Bike masses are assumed.** No peer-reviewed source for as-raced TT bike
   mass was found.
6. **LT1 is assumed.** No lactate data by rider type were found, so LT1 is
   set to 75% of LT2 for every profile. It matters: LT1 is where fatigue
   starts and the floor critical power sinks towards.
7. **No long efforts in the fit.** Powers for an hour or more would let
   $\tau_F$ (and with two of them $\gamma$) be fitted per profile. *To
   check:* whether the record power profile tables go that far.

## References

- Defraeye T, Blocken B, Koninckx E, Hespel P, Carmeliet J (2010).
  Aerodynamic study of different cyclist positions: CFD analysis and
  full-scale wind-tunnel tests. *Journal of Biomechanics* 43(7):1262–1268.
  doi:10.1016/j.jbiomech.2010.01.025
- Ebert TR, Martin DT, McDonald W, Victor J, Plummer J, Withers RT (2005).
  Power output during women's World Cup road cycle racing. *European Journal
  of Applied Physiology* 95(5–6):529–536. doi:10.1007/s00421-005-0039-y
- Garcia-Lopez J, Ogueta-Alday A, Larrazabal J, Rodriguez-Marroyo JA (2014).
  The use of velodrome tests to evaluate aerodynamic drag in professional
  cyclists. *International Journal of Sports Medicine* 35(5):451–455.
  doi:10.1055/s-0033-1355352
- Horvath M, Andersson EP (2025). Optimal body mass normalization of power
  output for accurate prediction of estimated cycling performance over
  complex time-trial courses. *Frontiers in Sports and Active Living*
  7:1599319. doi:10.3389/fspor.2025.1599319 (cross-check only)
- Impellizzeri FM, Ebert T, Sassi A, Menaspà P, Rampinini E, Martin DT
  (2008). Level ground and uphill cycling ability in elite female mountain
  bikers and road cyclists. *European Journal of Applied Physiology*
  102(3):335–341. doi:10.1007/s00421-007-0590-9
- Martin JC, Milliken DL, Cobb JE, McFadden KL, Coggan AR (1998). Validation
  of a mathematical model for road cycling power. *Journal of Applied
  Biomechanics* 14(3):276–291.
- Mateo-March M, van Erp T, Muriel X, Valenzuela PL, Zabala M, Lamberts RP,
  Lucia A, Barranco-Gil D, Pallarés JG (2022). The record power profile in
  professional female cyclists: normative values obtained from a large
  database. *International Journal of Sports Physiology and Performance*
  17(5):682–686. doi:10.1123/ijspp.2021-0372
- Padilla S, Mujika I, Cuesta G, Goiriena JJ (1999). Level ground and uphill
  cycling ability in professional road cycling. *Medicine & Science in
  Sports & Exercise* 31(6):878–885. doi:10.1097/00005768-199906000-00017
- Valenzuela PL, Muriel X, van Erp T, Mateo-March M, Gandia-Soriano A,
  Zabala M, Lamberts RP, Lucia A, Barranco-Gil D, Pallarés JG (2022). The
  record power profile of male professional cyclists: normative values
  obtained from a large database. *International Journal of Sports
  Physiology and Performance* 17(5):701–710. doi:10.1123/ijspp.2021-0263
