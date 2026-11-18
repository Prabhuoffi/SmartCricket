# Demo upload files

This folder contains **10 JPG photos and 10 MP4 videos** for trying the existing upload and result pages. Sign in as a player, choose any `demo-photo*.jpg` on `/app/image.html` or any `demo-video*.mp4` on `/app/video.html`, and start analysis. The result opens on the app's existing report page and remains in History.

All MP4 files use H.264 video so they can play in the browser. The short clips are about one to two seconds long. The files in this folder are upload examples; the app generates new analysis data when you upload one.

| Photo | Source |
| --- | --- |
| `demo-photo.jpg` | Project test photo, `tests/samples/batter.jpg` |
| `demo-photo-02.jpg` | Existing `photo2_orig.jpg` upload |
| `demo-photo-03.jpg` | Existing `photo3_orig.jpg` upload |
| `demo-photo-04.jpg` | Existing `photo1_orig.jpg` upload |
| `demo-photo-05.jpg` | Existing `test.png` upload, converted to JPG |
| `demo-photo-06.jpg` | Existing `w.png` upload, converted to JPG |
| `demo-photo-07.jpg` | Existing `concept_frame.jpg` upload |
| `demo-photo-08.jpg` | Existing stadium lights photo upload, converted to JPG |
| `demo-photo-09.jpg` | Still frame from the `vid112_2.avi` sample clip |
| `demo-photo-10.jpg` | Still frame from an existing upper cut demo clip |

| Video | Content |
| --- | --- |
| `demo-video.mp4` | Cover drive project test clip |
| `demo-video-02.mp4` | Defensive shot |
| `demo-video-03.mp4` | Down the wicket shot |
| `demo-video-04.mp4` | Flick |
| `demo-video-05.mp4` | Practice clip, shot 1 |
| `demo-video-06.mp4` | Practice clip, shot 2 |
| `demo-video-07.mp4` | Practice clip, shot 3 |
| `demo-video-08.mp4` | Upper cut demo, shot 1 |
| `demo-video-09.mp4` | Upper cut demo, shot 2 |
| `demo-video-10.mp4` | `vid112_2.avi` sample, converted to MP4 |

You can also place your own JPG, PNG, MP4, MOV, or AVI files here and upload them in the same way. Photos must be at most 10 MB and videos at most 50 MB. The app saves uploads in `data/uploads/` and generated media in `data/outputs/`.

Photo credit: `demo-photo.jpg` comes from Acabashi, Wikimedia Commons, CC BY-SA 4.0. Video source rights remain with their owners; see the [project's data and image credits](../README.md#data-and-image-credits). These files are for local demo and non-commercial research use.
