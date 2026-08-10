# Third-party Sources

Large external repositories are not vendored in this GitHub project. Keep this directory as a local cache only when building on Jetson.

## Optional Local Sources

The scripts may create these directories locally:

```text
third_party/jetson-inference
third_party/jetson-device-skills
third_party/jetson-bsp-skills
```

Recommended source URLs:

```text
https://github.com/dusty-nv/jetson-inference.git
https://github.com/NVIDIA-AI-IOT/jetson-device-skills
https://github.com/NVIDIA-AI-IOT/jetson-bsp-skills
```

## Build Rule

When `jetson-inference` is present locally or on Jetson, build inside its own source tree:

```bash
cd third_party/jetson-inference
mkdir -p build
cd build
cmake -DBUILD_DEPS=NO -DBUILD_INTERACTIVE=NO ../
make -j1
sudo make install
sudo ldconfig
```

Do not build from `/data/build` or the repository root.

