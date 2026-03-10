"""V3 Value Engine."""
__version__ = "3.0.0"
__author__ = "Madhur Kapadia"
__all__ = ["RegimeClassifier", "ValueScanner", "BacktestEngine", "MarketAnalyzer"]

def __getattr__(name):
    if name == "RegimeClassifier":
        from engine.regime import RegimeClassifier
        return RegimeClassifier
    elif name == "MarketAnalyzer":
        from engine.market_analyzer import MarketAnalyzer
        return MarketAnalyzer
    raise AttributeError(f"module 'engine' has no attribute {name!r}")
