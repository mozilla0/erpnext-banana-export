from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="banana_export",
    version="1.0.0",
    description="Banana Buchhaltung CSV Export für Joker IT AG",
    author="Joker IT AG",
    author_email="info@jokerit.ch",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
