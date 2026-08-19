# Contributing to `aws-auth`

Thank you for your interest in contributing to `aws-auth`!

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork**:
   ```bash
   git clone https://github.com/\<your-username\>/aws-auth.git
   cd aws-auth
   ```
3. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. **Install development dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install -e .
   ```

## Running Tests

Run the full test suite before submitting pull requests:
```bash
python -m unittest discover tests
```

## Pull Request Guidelines

- Create a feature branch (`git checkout -b feature/amazing-feature`).
- Ensure all tests pass.
- Write unit tests for new features or bug fixes.
- Keep pull requests focused on a single topic.
