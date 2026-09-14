# Contributing to EcoSim

Thank you for your interest in contributing to EcoSim! 🎉

## How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add some amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## Development Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
Copy-Item .env.example .env
```

## Code Standards

- Follow the existing code style
- Write tests for new features (`python -m pytest`)
- Ensure lint passes (`npm run lint`)
- Type check (`npx tsc --noEmit`)
- Update documentation as needed

## Reporting Issues

- Use the [Bug Report](https://github.com/Emon0036/EcosimAi-/issues/new?template=bug_report.md) template for bugs
- Use the [Feature Request](https://github.com/Emon0036/EcosimAi-/issues/new?template=feature_request.md) template for features

## Questions?

Feel free to open an issue or reach out to the maintainer.

## Code of Conduct

Please be respectful and constructive in all interactions. See [Code of Conduct](CODE_OF_CONDUCT.md) for details.
