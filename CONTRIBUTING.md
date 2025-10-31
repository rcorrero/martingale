# Contributing to Martingale

We love your input! We want to make contributing to Martingale as easy and transparent as possible.

## Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

## Pull Requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project.

## Report bugs using GitHub's [issue tracker](https://github.com/yourusername/martingale/issues)

We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/yourusername/martingale/issues/new).

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## Code Style

* Use meaningful variable and function names
* Add comments for complex logic
* Follow PEP 8 for Python code
* Use consistent indentation (4 spaces for Python, 2 spaces for JavaScript)
* Keep functions small and focused

## Development Setup

1. Fork and clone the repository
2. Create a virtual environment: `python3 -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and configure
6. Run the application: `python app.py`

## Testing

Currently, the project doesn't have automated tests, but we welcome contributions to add them! Areas that would benefit from testing:

- API endpoints
- Portfolio calculations
- Trading logic
- Authentication

## License

By contributing, you agree that your contributions will be licensed under its MIT License.