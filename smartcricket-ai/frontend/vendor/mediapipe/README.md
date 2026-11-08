# MediaPipe browser runtime

These runtime files are copied from the npm package `@mediapipe/tasks-vision` version `1.2.0` so the live camera page can load without a CDN request. The package is published by Google under Apache-2.0; see [LICENSE-2.0.txt](LICENSE-2.0.txt).

The app uses `vision_bundle.mjs` and the SIMD or non-SIMD WebAssembly pair in `wasm/`. The pose model remains in `models/pose_landmarker_full.task` and is served by the backend to signed-in players.
