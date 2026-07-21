"""
PGEA系列驱控一体式工业平行电爪 - Python控制库安装脚本
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pgea-gripper-skill",
    version="1.0.0",
    author="AI Assistant",
    description="大寰(DH-Robotics) PGEA系列驱控一体式工业平行电爪Python控制库",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.dh-robotics.com",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Manufacturing",
        "Topic :: Scientific/Engineering :: Human Machine Interfaces",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "pyserial>=3.4",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.9",
        ],
    },
    keywords="gripper, robot, automation, modbus, pgea, dh-robotics, 夹爪, 机器人",
    project_urls={
        "Manufacturer": "https://www.dh-robotics.com",
        "Documentation": "https://www.dh-robotics.com/download",
    },
)
