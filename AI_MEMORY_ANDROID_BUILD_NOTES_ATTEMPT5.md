# ai-memory Android ARM64 build — attempt 5

Root cause from attempt 3: rustc reported `E0463: can't find crate for core` for `aarch64-linux-android`, despite the rust-toolchain action reporting success. The workflow now explicitly runs `rustup target add aarch64-linux-android --toolchain stable`, records installed targets and the target libdir, asserts the target libraries exist, and invokes `cargo +stable ndk`.

Scope: isolated branch `ai-memory-v2.6.4-android-build`. No changes to `~/GTA/BR`, Hazewave, or global agent configuration.