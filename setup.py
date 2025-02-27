from setuptools import setup, find_packages

setup(
    name='crowdcores-node',
    version='1.1.3',
    packages=find_packages(),
    install_requires=[
        'websockets',
        'torch',
        'transformers',

    ],
    entry_points={
        'console_scripts': [
            'crowdcores-node = crowdcores_node.manager:main'
        ]
    }
)
