"""
Flask-RAGE
-------------------

Flask logging addon inspired by RoR's lograge gem
"""
from setuptools import setup

setup(
    name='Flask-RAGE',
    version='0.1',
    url='https://github.com/airhelp/flask-rage/',
    license='MIT',
    description='Flask logging addon inspired by lograge',
    long_description=__doc__,
    keywords=['flask', 'logging', 'json', 'lograge'],
    py_modules=['flask_rage'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=['Flask'],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Logging',
    ]
)
