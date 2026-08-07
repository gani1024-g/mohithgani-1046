while True:
    s=input("Enter a string: ")
    freq={}
    for char in s:
        if char in freq:
            freq[char]+=1
        else:
            freq[char]=1
    print("Character frequencies:")
    for char, count in freq.items():
        print(f"'{char}': {count}")
    print("Total characters present:", len(s))