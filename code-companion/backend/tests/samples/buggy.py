"""Sample file with intentional issues, used by tests and for manual testing."""
password = "hardcoded-secret-123"


def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def add_item(item, items=[]):
    items.append(item)
    return items


try:
    x = 1 / 0
except:
    pass


def build_query(name):
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    return query


for i in range(10):
    for j in range(10):
        pass
