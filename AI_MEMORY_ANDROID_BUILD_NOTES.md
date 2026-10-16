# ai-memory Android ARM64 build experiment

This isolated branch builds the official `akitaonrails/ai-memory` v2.6.4 source for Android `aarch64-linux-android`.

The workflow corrects cargo-ndk argument parsing by omitting the misplaced `-p 26` argument and aligns `ANDROID_NDK`, `ANDROID_NDK_HOME`, and `ANDROID_NDK_ROOT` to NDK 27.2.12479018.

No BR-no-GTA or Hazewave files are changed by this experiment.
