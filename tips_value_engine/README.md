# Tips Value Engine 1.0

Python/Streamlit MVP for analyse af Tips 4–13.

## Funktioner
- Henter kommende fodboldodds fra The Odds API (egen API-nøgle kræves).
- Fjerner bookmaker-margin og beregner fair 1/X/2-markedsprocenter.
- Sammenligner egne sandsynligheder med marked og spillerpopularitet.
- Beregner en screeningsscore (ikke ROI).
- Kuponbudget og fuldt matematisk rækkeantal.
- Historisk multiclass Brier score.
- CSV-import til Tips-spillerprocenter og historiske data.

## Vigtigt om økonomisk værdi
Tips er et puljespil. Ægte forventet ROI kan ikke beregnes ud fra odds og spillerpopularitet alene. Det kræver bl.a. præmiepulje, præmiefordeling, rækkepris, officielle systemregler og et estimat af de øvrige spilleres fulde kuponer. MVP'en viser derfor ikke et falsk ROI-tal.

## Installation – Windows
1. Installer Python 3.11 eller nyere.
2. Pak ZIP-filen ud.
3. Åbn PowerShell i projektmappen.
4. Kør:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

5. Indsæt din The Odds API-nøgle i `.env`.
6. Start dashboard:

```powershell
streamlit run app.py
```

Browseren åbner normalt på http://localhost:8501.

## Installation – macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## CSV-format: odds og sandsynligheder

Påkrævede odds-kolonner:
- `match`
- `odds_1`
- `odds_x`
- `odds_2`

Valgfrie spillerandele:
- `players_1`
- `players_x`
- `players_2`

Valgfrie egne modelprocenter:
- `p_1`
- `p_x`
- `p_2`

Procenter angives som decimaler: 45 % = `0.45`.

## Historisk backtest CSV

Kolonner: `p1,px,p2,result`, hvor result er `1`, `X` eller `2`.

## Test

```bash
pytest -q
```

## Datakilder og næste skridt
- The Odds API: bookmakerodds og kommende events. API-nøgle og kvoter afhænger af udbyderens vilkår.
- Danske Spils Tips-procenter: indlæses via CSV i MVP'en. En officiel, stabil og tilladt automatiseringskilde skal verificeres, før connectoren aktiveres.
- Historiske Tips-resultater, præmiepuljer og systemgarantier: skal indsamles og versionsstyres særskilt.

## Roadmap
1. Verificeret import af Danske Spils Tips-procenter.
2. Historisk datalager med tidsstempler på odds og spillerandele.
3. Sandsynlighedsmodel (baseline: marked; senere Elo/Poisson og kalibrering).
4. Backtest med tidsbaseret train/test-split.
5. Monte Carlo-simulering af kuponer og puljedeling.
6. Systemoptimering, der bruger officielle R/U-systemnøgler og budget.
