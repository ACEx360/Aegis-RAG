# Diagram Rendering Instructions

## Available Renderers

| Tool | Status |
|------|--------|
| Node.js | v24.14.0 — available |
| npx mmdc (Mermaid CLI via npx) | v12.0.0 — available via `npx @mermaid-js/mermaid-cli` |
| Graphviz dot | Not installed |
| Java / PlantUML | Not installed |
| Inkscape | Not installed |

## Important: Chromium Download Warning

`npx @mermaid-js/mermaid-cli` requires Puppeteer, which downloads Chromium
(approximately 170 MB) on first run. **Do not run the render command below
without permission.**

Confirm with the project authors before running:

```
npx -y @mermaid-js/mermaid-cli -i figures\fig4_1_architecture.mmd -o figures\fig4_1_architecture.png --theme neutral --backgroundColor white --width 1200 --height 900
```

## Render All Diagrams (run from report/ directory)

```powershell
# Run once to download Chromium and render all .mmd files
$mmd_files = Get-ChildItem figures\*.mmd
foreach ($f in $mmd_files) {
    $out = $f.FullName -replace '\.mmd$', '.png'
    Write-Host "Rendering $($f.Name) ..."
    npx -y @mermaid-js/mermaid-cli -i $f.FullName -o $out --theme neutral --backgroundColor white --width 1400 --height 1000
}
```

## Manual Alternative (Mermaid Live Editor)

1. Open https://mermaid.live
2. Paste the content of each `.mmd` file
3. Click Download PNG
4. Save as the corresponding `.png` filename in `report/figures/`
5. Required resolution: at minimum 1200 × 900 pixels (300 dpi equivalent)

## Diagram Files

| File | Figure | Description |
|------|--------|-------------|
| fig1_1_overview.mmd | 1.1 | System Overview |
| fig3_1_sdlc.mmd | 3.1 | SDLC Model |
| fig4_1_architecture.mmd | 4.1 | System Architecture |
| fig4_2_dfd0.mmd | 4.2 | DFD Level 0 |
| fig4_3_dfd1.mmd | 4.3 | DFD Level 1 |
| fig4_4_dfd2.mmd | 4.4 | DFD Level 2 |
| fig4_5_er.mmd | 4.5 | ER Diagram |
| fig4_6_usecase.mmd | 4.6 | Use Case Diagram |
| fig4_7_sequence.mmd | 4.7 | Sequence Diagram |
| fig4_8_class.mmd | 4.8 | Class Diagram |
| fig4_9_component.mmd | 4.9 | Component Diagram |
| fig4_10_deployment.mmd | 4.10 | Deployment Diagram |
| fig4_11_state.mmd | 4.11 | State Machine |
| fig5_1_timeline.mmd | 5.1 | Project Timeline |
| fig5_2_tasknet.mmd | 5.2 | Task Network |
| fig6_1_modules.mmd | 6.1 | Module Dependency |
| fig6_2_fusion.mmd | 6.2 | Fusion Flowchart |
| fig6_3_verify.mmd | 6.3 | Verification Flowchart |

## Screenshot Placeholders

Figures 8.3–8.10 are screenshots. Save them as:
`fig8_3_priority_tab.png` through `fig8_10_swagger.png`

See Chapter 8 markdown for the exact screen and state to capture for each.

