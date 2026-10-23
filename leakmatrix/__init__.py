"""LeakMatrix — continuous cross-tenant authorization testing.

Parses any OpenAPI/Swagger spec, builds a cross-tenant request matrix
(attacker credentials x victim identifiers), runs it with strict rate
limits, and classifies responses to surface real data leaks.
"""

__version__ = "0.3.0"
