# SmartCricket mobile

The mobile app signs in to the same backend as the website. The login screen
only asks for the player email and password. Its backend address is configured
in `lib/data/app_config.dart` or with the `API_BASE_URL` build setting.

## Sign in from an Android phone

1. Put the phone and Mac on the same Wi-Fi network.
2. From `smartcricket-ai`, start a backend that listens on the network:

   ```sh
   .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8002
   ```

   Port 8002 leaves the existing `localhost:8000` and `localhost:8001`
   servers alone. If port 8002 is occupied later, choose another free port.

3. On the Mac, find its Wi-Fi address with `ifconfig en0 | awk '/inet / {print $2}'`.
   Open `http://MAC_IP:8002/api/health` on the phone. It should show
   `"status":"ok"`.
4. Open the app and use the same player email and password as the website. The
   current local build targets `http://10.88.13.145:8002` automatically and
   checks the health endpoint before sending the password.

The Android app includes Internet permission and allows local HTTP for this
development setup. Use a trusted local network. Public deployments should use
a valid HTTPS server address.

## Live practice

The camera and pose tracking run on the phone. During clear full-body arm and
wrist movement, the app automatically keeps one shot frame in temporary storage. Tapping
**Finish** saves the measured session and uploads that still to the player's
account. The recap shows the image and whether it reached the server; saved
images also appear in the website's Progress page. If no clear pose was found,
the session saves without an image.
Saved sessions and images are available through **Live history** in the app and
**History** on the website. Deleting an image keeps the session; deleting the
session removes its image and live-session XP.

The speaker button turns spoken coaching on or off. Tap the microphone and ask
**“How do I play a front foot shot?”** or **“Show me the hook shot.”** The guide
speaks the steps and loops a three-phase movement illustration. **Learn a shot**
opens the same guide by name without speech recognition. The existing
**pause**, **resume**, **reset**, and **finish** commands also work. For a name
outside the built-in guides, the app asks the AI Coach for a text explanation
when that service is configured; it cannot show a movement illustration for
that name.

If the Mac's IP or backend port changes, rebuild with
`flutter run --dart-define=API_BASE_URL=http://MAC_IP:8002`. For an Android
emulator, use `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.
