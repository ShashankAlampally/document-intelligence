# Frontend layout verification

The layout was checked in the browser at 1440 × 900 and 390 × 844. The populated previews use clearly labelled sample data from `tests/visual-preview.tsx`; they do not call the backend or ship in the production bundle.

Verified: independent conversation scrolling, visible composer, extraction controls, wrapping filenames and page/section badges, folder-panel toggle, evidence-panel open/close, and next-source navigation. Document width and height match the viewport at both sizes, without page overflow.

- `desktop.png`: desktop populated workspace.
- `mobile.png`: mobile extraction controls.
- Dev-only populated preview: http://127.0.0.1:5173/tests/visual-preview.html
- Application: http://127.0.0.1:5173

`npm run build` passed and updates `frontend/dist` for the locally served FastAPI frontend. The 10 existing frontend tests passed. If running Docker, rebuild the image from the repository root with `docker compose up -d --build`, then refresh the browser. The Docker runtime itself was not tested in this UI pass.
