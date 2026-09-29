# Third-party notices

palm-lab itself is released under the MIT licence (see `LICENSE`). It is built
on the following work, some of which is included in the app you download.

| Component | Licence | What palm-lab uses it for |
| --- | --- | --- |
| [Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) by Microsoft | MIT | Interface icons in the window |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) and its hand landmarker model, by Google | Apache 2.0 | Finding hands in camera frames |
| [OpenCV](https://opencv.org/license/) | Apache 2.0 | Reading the camera |
| [NumPy](https://numpy.org/doc/stable/license.html) | BSD 3-Clause | Image data |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD 3-Clause | The window |
| [pythonnet](https://github.com/pythonnet/pythonnet) | MIT | pywebview's bridge to Windows |
| [pystray](https://github.com/moses-palmer/pystray) | LGPL 3.0 | The icon in the notification area |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU | Loading that icon's image |
| [Microsoft Edge WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) | Part of Windows | Drawing the window |

The full licence texts are available at the links above. pystray's licence
texts (GPL 3.0 and LGPL 3.0) are also included in the installed app, in its
`pystray-*.dist-info` folder. As the LGPL allows, you can use a different
version of pystray by building palm-lab from its source code. The Fluent icons'
notice is reproduced here because their path data is copied into
`src/palm_lab/ui/static/app.js`.

## Fluent UI System Icons

MIT License

Copyright (c) 2020 Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
