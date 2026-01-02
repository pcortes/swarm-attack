"""Tests for SOLIDChecker SOLID principle violation detection.

TDD RED Phase: These tests define the expected behavior of SOLIDChecker.
Tests cover:
- Single Responsibility Principle (SRP) violations
- Open/Closed Principle (OCP) violations
- Dependency Inversion Principle (DIP) violations
"""

import ast
from pathlib import Path

import pytest

from swarm_attack.code_quality.solid_checker import SOLIDChecker
from swarm_attack.code_quality.models import Finding, Severity, Category


class TestSOLIDCheckerInit:
    """Tests for SOLIDChecker initialization."""

    def test_creates_instance(self):
        """SOLIDChecker should initialize without errors."""
        checker = SOLIDChecker()
        assert checker is not None


class TestSRPViolationDetection:
    """Tests for detecting Single Responsibility Principle violations.

    A class violates SRP if it has methods from multiple unrelated domains.
    Uses method clustering - if methods form > 2 distinct clusters, flag SRP.
    """

    def test_detects_srp_violation_multiple_responsibilities(self, tmp_path):
        """Class with database, email, and logging methods should be flagged."""
        code = '''
class UserManager:
    """A god class with multiple unrelated responsibilities."""

    def __init__(self):
        self.users = []
        self.db_connection = None
        self.email_client = None

    # Database-related methods (cluster 1)
    def connect_to_database(self, connection_string):
        """Connect to database."""
        self.db_connection = connection_string

    def save_to_database(self, user):
        """Save user to database."""
        pass

    def load_from_database(self, user_id):
        """Load user from database."""
        pass

    def delete_from_database(self, user_id):
        """Delete user from database."""
        pass

    # Email-related methods (cluster 2)
    def send_email(self, to, subject, body):
        """Send an email."""
        pass

    def send_welcome_email(self, user):
        """Send welcome email to new user."""
        pass

    def send_notification_email(self, user, message):
        """Send notification email."""
        pass

    # Logging-related methods (cluster 3)
    def log_activity(self, message):
        """Log user activity."""
        pass

    def log_error(self, error):
        """Log error."""
        pass

    def export_logs(self, path):
        """Export logs to file."""
        pass
'''
        file_path = tmp_path / "test_srp_violation.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        srp_findings = [
            f for f in findings
            if "srp" in f.title.lower() or "single responsibility" in f.title.lower()
        ]
        assert len(srp_findings) >= 1
        finding = srp_findings[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.category == Category.SOLID
        assert "UserManager" in finding.description or "UserManager" in finding.title

    def test_does_not_flag_focused_class(self, tmp_path):
        """Class with single responsibility should NOT be flagged."""
        code = '''
class UserRepository:
    """Repository class focused on database operations."""

    def __init__(self, connection):
        self.connection = connection

    def save(self, user):
        """Save user to database."""
        pass

    def load(self, user_id):
        """Load user from database."""
        pass

    def delete(self, user_id):
        """Delete user from database."""
        pass

    def find_by_email(self, email):
        """Find user by email."""
        pass
'''
        file_path = tmp_path / "test_focused_class.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        srp_findings = [
            f for f in findings
            if "srp" in f.title.lower() or "single responsibility" in f.title.lower()
        ]
        assert len(srp_findings) == 0

    def test_ignores_dunder_methods(self, tmp_path):
        """Dunder methods (__init__, __str__) should not count towards clusters."""
        code = '''
class User:
    """A simple data class."""

    def __init__(self, name, email):
        self.name = name
        self.email = email

    def __str__(self):
        return f"User({self.name})"

    def __repr__(self):
        return self.__str__()

    def get_display_name(self):
        return self.name.title()

    def get_email_domain(self):
        return self.email.split("@")[1]
'''
        file_path = tmp_path / "test_dunder.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        srp_findings = [
            f for f in findings
            if "srp" in f.title.lower() or "single responsibility" in f.title.lower()
        ]
        assert len(srp_findings) == 0


class TestOCPViolationDetection:
    """Tests for detecting Open/Closed Principle violations.

    Look for switch/if-elif chains checking isinstance or type.
    These should be replaced with polymorphism.
    """

    def test_detects_ocp_violation_isinstance_chain(self, tmp_path):
        """if/elif chain with isinstance checks should be flagged."""
        code = '''
class ShapeCalculator:
    """Calculator that uses isinstance checks instead of polymorphism."""

    def calculate_area(self, shape):
        """Calculate area based on shape type - OCP violation."""
        if isinstance(shape, Circle):
            return 3.14159 * shape.radius ** 2
        elif isinstance(shape, Rectangle):
            return shape.width * shape.height
        elif isinstance(shape, Triangle):
            return 0.5 * shape.base * shape.height
        elif isinstance(shape, Square):
            return shape.side ** 2
        else:
            raise ValueError("Unknown shape type")
'''
        file_path = tmp_path / "test_ocp_isinstance.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        ocp_findings = [
            f for f in findings
            if "ocp" in f.title.lower() or "open/closed" in f.title.lower() or "open-closed" in f.title.lower()
        ]
        assert len(ocp_findings) >= 1
        finding = ocp_findings[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.category == Category.SOLID

    def test_detects_ocp_violation_type_check(self, tmp_path):
        """if/elif chain with type() checks should be flagged."""
        code = '''
def process_message(message):
    """Process message based on type - OCP violation."""
    if type(message) == TextMessage:
        return handle_text(message)
    elif type(message) == ImageMessage:
        return handle_image(message)
    elif type(message) == VideoMessage:
        return handle_video(message)
    elif type(message) == AudioMessage:
        return handle_audio(message)
'''
        file_path = tmp_path / "test_ocp_type.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        ocp_findings = [
            f for f in findings
            if "ocp" in f.title.lower() or "open/closed" in f.title.lower() or "open-closed" in f.title.lower()
        ]
        assert len(ocp_findings) >= 1

    def test_does_not_flag_single_isinstance(self, tmp_path):
        """Single isinstance check should NOT be flagged - only chains."""
        code = '''
def validate_input(value):
    """Single isinstance check is fine."""
    if isinstance(value, str):
        return value.strip()
    return str(value)
'''
        file_path = tmp_path / "test_single_isinstance.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        ocp_findings = [
            f for f in findings
            if "ocp" in f.title.lower() or "open/closed" in f.title.lower() or "open-closed" in f.title.lower()
        ]
        assert len(ocp_findings) == 0

    def test_does_not_flag_polymorphic_code(self, tmp_path):
        """Code using polymorphism instead of type checks should NOT be flagged."""
        code = '''
class Shape:
    """Base shape with abstract area method."""
    def area(self):
        raise NotImplementedError


class Circle(Shape):
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        return 3.14159 * self.radius ** 2


class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height


def calculate_total_area(shapes):
    """Uses polymorphism - no type checking needed."""
    return sum(shape.area() for shape in shapes)
'''
        file_path = tmp_path / "test_polymorphic.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        ocp_findings = [
            f for f in findings
            if "ocp" in f.title.lower() or "open/closed" in f.title.lower() or "open-closed" in f.title.lower()
        ]
        assert len(ocp_findings) == 0


class TestDIPViolationDetection:
    """Tests for detecting Dependency Inversion Principle violations.

    Look for classes that instantiate their dependencies directly
    in __init__ instead of accepting them as parameters.
    """

    def test_detects_dip_violation_direct_instantiation(self, tmp_path):
        """Class that creates dependencies in __init__ should be flagged."""
        code = '''
class OrderService:
    """Service that violates DIP by creating its own dependencies."""

    def __init__(self):
        # DIP violations - creating concrete dependencies
        self.database = MySQLDatabase()
        self.email_service = SMTPEmailService()
        self.payment_processor = StripePaymentProcessor()
        self.logger = FileLogger("orders.log")

    def process_order(self, order):
        self.database.save(order)
        self.email_service.send_confirmation(order)
        self.payment_processor.charge(order)
'''
        file_path = tmp_path / "test_dip_violation.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        dip_findings = [
            f for f in findings
            if "dip" in f.title.lower() or "dependency inversion" in f.title.lower()
        ]
        assert len(dip_findings) >= 1
        finding = dip_findings[0]
        assert finding.severity == Severity.MEDIUM
        assert finding.category == Category.SOLID
        assert "OrderService" in finding.description or "OrderService" in finding.title

    def test_does_not_flag_dependency_injection(self, tmp_path):
        """Class that receives dependencies via __init__ should NOT be flagged."""
        code = '''
class OrderService:
    """Service that follows DIP with dependency injection."""

    def __init__(self, database, email_service, payment_processor, logger):
        # Dependencies injected - follows DIP
        self.database = database
        self.email_service = email_service
        self.payment_processor = payment_processor
        self.logger = logger

    def process_order(self, order):
        self.database.save(order)
        self.email_service.send_confirmation(order)
        self.payment_processor.charge(order)
'''
        file_path = tmp_path / "test_di.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        dip_findings = [
            f for f in findings
            if "dip" in f.title.lower() or "dependency inversion" in f.title.lower()
        ]
        assert len(dip_findings) == 0

    def test_ignores_value_object_instantiation(self, tmp_path):
        """Creating simple value objects or data containers should NOT be flagged."""
        code = '''
class UserProfile:
    """Creates simple value objects - not a DIP violation."""

    def __init__(self, name, email):
        self.name = name
        self.email = email
        self.settings = {}  # dict is a value type
        self.created_at = datetime.now()  # datetime is a value type
        self.tags = []  # list is a value type
        self.config = {"default": True}  # dict literal
'''
        file_path = tmp_path / "test_value_objects.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        dip_findings = [
            f for f in findings
            if "dip" in f.title.lower() or "dependency inversion" in f.title.lower()
        ]
        assert len(dip_findings) == 0


class TestAnalyzeFile:
    """Tests for the main analyze_file method."""

    def test_returns_empty_list_for_clean_code(self, tmp_path):
        """Clean SOLID-compliant code should return no findings."""
        code = '''
class Repository:
    """A focused repository class."""

    def __init__(self, connection):
        self.connection = connection

    def save(self, entity):
        pass

    def load(self, entity_id):
        pass
'''
        file_path = tmp_path / "test_clean.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        assert len(findings) == 0

    def test_handles_syntax_error_gracefully(self, tmp_path):
        """Invalid Python code should return empty list, not crash."""
        code = '''
class Broken
    # Missing colon
    def method(self
        pass
'''
        file_path = tmp_path / "test_syntax_error.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        assert findings == []

    def test_handles_nonexistent_file_gracefully(self):
        """Non-existent file should return empty list, not crash."""
        checker = SOLIDChecker()
        findings = checker.analyze_file(Path("/nonexistent/path/file.py"))

        assert findings == []

    def test_finding_has_required_fields(self, tmp_path):
        """All findings should have required fields from spec."""
        code = '''
class GodClass:
    def db_save(self): pass
    def db_load(self): pass
    def db_delete(self): pass
    def email_send(self): pass
    def email_notify(self): pass
    def email_welcome(self): pass
    def log_info(self): pass
    def log_error(self): pass
    def log_debug(self): pass
'''
        file_path = tmp_path / "test_fields.py"
        file_path.write_text(code)

        checker = SOLIDChecker()
        findings = checker.analyze_file(file_path)

        assert len(findings) >= 1
        finding = findings[0]

        # Check required fields from spec
        assert finding.finding_id is not None
        assert finding.severity in Severity
        assert finding.category == Category.SOLID
        assert finding.file == str(file_path)
        assert finding.line > 0
        assert finding.title is not None
        assert finding.description is not None


class TestClusterMethodsByName:
    """Tests for the _cluster_methods_by_name helper method."""

    def test_clusters_by_common_prefix(self):
        """Methods with common prefixes should be grouped together."""
        code = '''
class TestClass:
    def save_user(self): pass
    def save_order(self): pass
    def save_product(self): pass
    def load_user(self): pass
    def load_order(self): pass
'''
        tree = ast.parse(code)
        class_node = tree.body[0]

        checker = SOLIDChecker()
        clusters = checker._cluster_methods_by_name(class_node)

        # Should have 2 clusters: save_* and load_*
        assert len(clusters) == 2

    def test_single_method_not_clustered(self):
        """Single method should form its own cluster."""
        code = '''
class TestClass:
    def process(self): pass
'''
        tree = ast.parse(code)
        class_node = tree.body[0]

        checker = SOLIDChecker()
        clusters = checker._cluster_methods_by_name(class_node)

        assert len(clusters) == 1


class TestFindTypeChecks:
    """Tests for the _find_type_checks helper method."""

    def test_finds_isinstance_checks(self):
        """Should find isinstance calls in if/elif chains."""
        code = '''
def process(obj):
    if isinstance(obj, str):
        pass
    elif isinstance(obj, int):
        pass
    elif isinstance(obj, list):
        pass
'''
        tree = ast.parse(code)

        checker = SOLIDChecker()
        type_checks = checker._find_type_checks(tree)

        # Should find 3 isinstance checks
        assert len(type_checks) >= 3

    def test_finds_type_checks(self):
        """Should find type() checks in if/elif chains."""
        code = '''
def process(obj):
    if type(obj) == str:
        pass
    elif type(obj) == int:
        pass
'''
        tree = ast.parse(code)

        checker = SOLIDChecker()
        type_checks = checker._find_type_checks(tree)

        # Should find 2 type checks
        assert len(type_checks) >= 2

    def test_returns_line_and_type(self):
        """Should return tuple of (line_number, type_being_checked)."""
        code = '''
def process(obj):
    if isinstance(obj, MyClass):
        pass
'''
        tree = ast.parse(code)

        checker = SOLIDChecker()
        type_checks = checker._find_type_checks(tree)

        assert len(type_checks) >= 1
        line, type_name = type_checks[0]
        assert isinstance(line, int)
        assert isinstance(type_name, str)
