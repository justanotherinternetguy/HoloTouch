# HoloTouch

> we made jarvis, yo

![jarvis](4d914bbad1694af7e3d9cc78270a7f14.gif)

theme: _navigation_

team HAASHtag's (Hendry, Ariana, Arthur, Song Han)'s submission for BigRedHacks 2026.

> navigating HCI, reimagined.

# problem

We have all seen attempts at making spatial control for computers ([handy](https://github.com/Vin124/handy), [mitsu](https://devpost.com/software/mitsu-hand-and-voice-gesture-control-for-the-desktop), and [gesturecontrol](https://github.com/Mizuna737/gesturecontrol)). However, they **all suck**.

Why do they suck?

- literally just mapping your hand to cursor position
  - boring! no one wants a bastardization of spatial HCI by forcing your hand to become a mouse cursor.
- unintuitive gestures w/ low gesture count
- no usage of 3D space and other non-manual controls

All previous solutions are just an attempt to stuff spatial HCI **on top** of an outdated keyboard-mouse interaction framework.

# inspiration

JARVIS!!!!

# design goals

HoloTouch is designed to be...

- **intuitive** with easy gestures for human hands
- **extensible** with custom gesture creation and fine-tuning
- **3D space-first** by using all the space around the user and using facial features to locate gestures
- **quick**, **responsive,**, and **consistent**, making it an **actually viable replacement** for keyboard-mouse control

HoloTouch is the **closest** you will get to tony stark tossing windows around.

# how we built it

HoloTouch uses the built-in webcam to compute a total of >500 landmark/feature points across the user's face, hands, and forearms. We use Mediapipe for most of this computation, although we augment with a small, custom-trained neural net.

# challenges we ran into

We had to solve a longstanding problem in CV called **occlusion**. With complex hand motions, Mediapipe-generated landmark points often get too cluttered and overlap with each other, causing gesture detection to be unreliable. We solve this through a small custom neural net (fully connected MLP using a subset of the landmark features) that takes into account for a few hundred ms of previous gestures and can look-ahead predict what gesture might come next.

# accomplishments that we're proud of

HoloTouch is consistent and intuitive enough to **not be a gimmick anymore**. In fact, I have been using HoloTouch to skip songs when I'm working and minimize some windows. The fact that Holotouch can **actually** be used in my workflow and **improve** my quality of life shows how well-executed it is.

# what we learned

Accurate, quick, intuitive, and consistent spatial computing **is possible.** With perhaps a higher resolution camera and a little better hardware, Tony Stark's JARVIS is just a few years away.
