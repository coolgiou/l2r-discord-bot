from distutils.core import setup      

setup(
    name='L2R Discord Bot',
    version='1.0',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.6'
    ],
    keywords='lineage lineage2revolution l2r discord',
    packages=['l2rdiscordbot'],
    install_requires=[
        'discord==0.0.2',
        'gspread==0.6.2',
        'numpy==1.14.0',
        'oauth2client==4.1.2',
        'opencv-python==3.4.0.12',
        'pandas==0.22.0',
        'pillow==5.0.0'
    ]
)
