"""Create a staff account without putting passwords or admin keys in command history."""
import getpass
import json
import urllib.error
import urllib.parse
import urllib.request


def main():
    address = input("Shared database HTTPS address: ").strip().rstrip("/")
    parsed = urllib.parse.urlparse(address)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit("Enter the HTTPS address of the deployed database service.")
    key = getpass.getpass("Administrator setup key (hidden): ")
    email = input("Staff email: ").strip()
    name = input("Staff display name: ").strip()
    password = getpass.getpass("Initial password (12+ characters, hidden): ")
    if password != getpass.getpass("Confirm password (hidden): "):
        raise SystemExit("Passwords do not match.")
    body = json.dumps({"email": email, "display_name": name, "password": password}).encode()
    request = urllib.request.Request(address + "/admin/users", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key,
                                              "User-Agent": "StatTracker/4.0.2"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        print("Staff account created:", result["email"])
    except urllib.error.HTTPError as error:
        try:
            print(json.loads(error.read()).get("error", "Account creation failed."))
        except ValueError:
            print("Account creation failed:", error.code)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
