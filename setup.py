from setuptools import find_packages, setup


setup(
    name="jetson-robot-vision-gateway",
    version="0.1.0",
    description="Edge vision gateway for Jetson Nano robotics demos",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.6",
)

