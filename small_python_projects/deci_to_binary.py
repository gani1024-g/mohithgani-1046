while True:
    user_input = input("Enter a decimal number (or 'q' to quit): ")
    if user_input.lower() == 'q' or user_input.strip() == '':
        print("Exiting program.")
        break

    try:
        n = int(user_input)
    except ValueError:
        print("Please enter a valid integer or 'q' to quit.")
        continue

    if n < 0:
        print("Please enter a non-negative integer.")
        continue

    if n == 0:
        print("Binary representation: 0")
    else:
        binary = ""
        temp = n
        while temp > 0:
            binary = str(temp % 2) + binary
            temp //= 2
        print("Binary representation:", binary)