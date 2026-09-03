"""Bundled sample inputs, reused by both the API (`/api/samples`) and the
test suite, so "sample code inputs for testing" live in exactly one place."""
from app.models import Language, SampleCode

PYTHON_BUGGY = '''"""User account helpers (intentionally contains issues for demo purposes)."""
import os

password = "hardcoded-super-secret"


def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def add_item(item, items=[]):
    items.append(item)
    return items


def run_report(rows):
    total = 0
    for row in rows:
        for col in row:
            total += col
    return total


def load_user(cursor, username):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(query)


try:
    risky_operation = 1 / 0
except:
    pass

result = fibonacci(30)
print(result)
'''

PYTHON_CLEAN = '''"""Simple, well-documented utility module."""
from functools import lru_cache


@lru_cache(maxsize=None)
def fibonacci(n: int) -> int:
    """Return the n-th Fibonacci number using memoized recursion."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def sum_positive(values: list[int]) -> int:
    """Return the sum of only the positive numbers in ``values``."""
    return sum(v for v in values if v > 0)
'''

JAVA_BUGGY = '''import java.util.Scanner;

public class UserService {
    private String password = "hardcoded123";

    public void login(String role, String input) {
        Scanner sc = new Scanner(System.in);
        if (input == "admin") {
            System.out.println("Admin logged in");
        }
        try {
            int x = 1 / 0;
        } catch (Exception e) {
        }
        for (int i = 0; i < 10; i++) {
            for (int j = 0; j < 10; j++) {
                System.out.println(i + j);
            }
        }
    }
}
'''

JAVA_CLEAN = '''/** Provides basic arithmetic helpers. */
public class MathUtils {

    /**
     * Returns the sum of all values in the given array.
     *
     * @param values the values to sum
     * @return the sum of all values
     */
    public static int sum(int[] values) {
        int total = 0;
        for (int value : values) {
            total += value;
        }
        return total;
    }
}
'''

SAMPLES = [
    SampleCode(
        id="python-buggy",
        title="Python: account helpers (buggy)",
        language=Language.PYTHON,
        description="Contains a hardcoded secret, SQL injection, mutable default arg, bare except, and unmemoized recursion.",
        code=PYTHON_BUGGY,
    ),
    SampleCode(
        id="python-clean",
        title="Python: math utils (clean)",
        language=Language.PYTHON,
        description="A small, well-documented, memoized implementation for comparison.",
        code=PYTHON_CLEAN,
    ),
    SampleCode(
        id="java-buggy",
        title="Java: UserService (buggy)",
        language=Language.JAVA,
        description="Contains a hardcoded secret, String == comparison bug, empty catch block, and a nested loop.",
        code=JAVA_BUGGY,
    ),
    SampleCode(
        id="java-clean",
        title="Java: MathUtils (clean)",
        language=Language.JAVA,
        description="A small, well-documented utility class for comparison.",
        code=JAVA_CLEAN,
    ),
]
