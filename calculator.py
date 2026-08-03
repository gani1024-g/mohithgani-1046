
def get_number(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Please enter a valid number.")


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero.")
    return a / b


def modulus(a, b):
    if b == 0:
        raise ZeroDivisionError("Cannot compute modulus with divisor zero.")
    return a % b


def power(a, b):
    return a ** b


def print_menu():
    print("\nCalculator")
    print("1. Addition")
    print("2. Subtraction")
    print("3. Multiplication")
    print("4. Division")
    print("5. Modulus")
    print("6. Power")
    print("7. Exit")


def main():
    print("Welcome to the calculator program!")

    while True:
        print_menu()
        choice = input("Choose an option (1-7): ").strip()

        if choice == "7":
            print("Goodbye!")
            break

        if choice not in {"1", "2", "3", "4", "5", "6"}:
            print("Please choose a valid option between 1 and 7.")
            continue

        a = get_number("Enter the first number: ")
        b = get_number("Enter the second number: ")

        try:
            if choice == "1":
                result = add(a, b)
                operation = "+"
            elif choice == "2":
                result = subtract(a, b)
                operation = "-"
            elif choice == "3":
                result = multiply(a, b)
                operation = "*"
            elif choice == "4":
                result = divide(a, b)
                operation = "/"
            elif choice == "5":
                result = modulus(a, b)
                operation = "%"
            elif choice == "6":
                result = power(a, b)
                operation = "^"

            print(f"\n{a} {operation} {b} = {result}\n")
        except ZeroDivisionError as error:
            print(error)


if __name__ == "__main__":
    main()
