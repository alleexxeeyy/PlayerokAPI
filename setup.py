from setuptools import setup, find_packages


def readme():
    with open("README.md", "r") as f:
        return f.read()


def req():
    with open("requirements.txt", "r") as f:
        return f.read().splitlines()


setup(
    name="playerokapi",
    version="1.0.1",
    author="3xtra (alleexxeeyy)",
    author_email="alexey.work@gmail.com",
    description="Неофициальный API для работы с торговой площадкой Playerok, основанный на запросах",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/alleexxeeyy/PlayerokAPI",
    packages=find_packages(),
    install_requires=req(),
    classifiers=[
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="python playerok playerokapi api requests websocket",
    project_urls={"Documentation": "https://playerokapi.readthedocs.io/ru/latest/"},
    python_requires=">=3.11",
)
