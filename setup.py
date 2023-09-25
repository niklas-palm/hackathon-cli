from setuptools import setup

setup(
    name="ai-cli",
    version="1.0",
    py_modules=["hackathon"],
    install_requires=["Click", "boto3"],
    entry_points="""
        [console_scripts]
        hack=hackathon:cli
    """,
)
