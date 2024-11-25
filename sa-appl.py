from flask import Flask, request, render_template
from kubernetes import client, config

app = Flask(__name__)

# Load Kubernetes configuration
config.load_kube_config()
v1 = client.CoreV1Api()
rbac_api = client.RbacAuthorizationV1Api()

user_group_mapping = {}  # Group -> List of users (short name and username)
user_role_mapping = {}  # Username -> Role details

# Utility function to create a namespace (group)
def create_namespace(name):
    try:
        v1.read_namespace(name)
        return f"Namespace '{name}' already exists.", False
    except client.exceptions.ApiException as e:
        if e.status == 404:
            namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
            try:
                v1.create_namespace(namespace)
                return f"Namespace '{name}' created successfully.", True
            except client.exceptions.ApiException as e:
                return f"An error occurred: {e}", False
        else:
            return f"An error occurred: {e}", False

# Utility function to create a RoleBinding for a user in a namespace
def create_user_rolebinding(namespace: str, username: str, role_name="admin"):
    role_ref = client.V1RoleRef(
        api_group="rbac.authorization.k8s.io",
        kind="ClusterRole",
        name=role_name
    )

    subject = client.V1Subject(
        kind="User",
        name=username,
        api_group="rbac.authorization.k8s.io"
    )

    role_binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(name=f"{username}-{role_name}-binding", namespace=namespace),
        role_ref=role_ref,
        subjects=[subject]
    )

    try:
        rbac_api.create_namespaced_role_binding(namespace=namespace, body=role_binding)
        return f"RoleBinding '{username}-{role_name}-binding' created in namespace '{namespace}'."
    except client.exceptions.ApiException as e:
        return f"An error occurred: {e}"

# Utility function to create a service account for a user
def create_service_account(namespace: str, short_name: str, username: str):
    service_account = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=short_name,
            labels={"hpc/long-account": username}  # Add the custom label
        )
    )

    try:
        v1.create_namespaced_service_account(namespace=namespace, body=service_account)
        return f"ServiceAccount '{short_name}' created in namespace '{namespace}' with label 'hpc/long-account: {username}'."
    except client.exceptions.ApiException as e:
        return f"An error occurred while creating the ServiceAccount: {e}"

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/add_group", methods=["GET", "POST"])
def add_group():
    message = ""
    if request.method == "POST":
        group_name = request.form.get("group_name")
        if group_name:
            message, created = create_namespace(group_name)
            if created:
                message += f" Namespace '{group_name}' is ready."
    return render_template("add_group.html", message=message)

@app.route("/list_groups")
def list_groups_page():
    try:
        namespaces = v1.list_namespace()
        group_namespaces = [ns.metadata.name for ns in namespaces.items]
    except client.exceptions.ApiException as e:
        group_namespaces = []
        print(f"An error occurred while listing namespaces: {e}")
    return render_template("list_groups.html", groups=group_namespaces)

@app.route("/add_users", methods=["GET", "POST"])
def add_users():
    message = ""
    if request.method == "POST":
        usernames = request.form.get("usernames")  # Comma-separated usernames
        short_names = request.form.get("short_names")  # Comma-separated short names
        group = request.form.get("group")
        role = request.form.get("role")

        if usernames and short_names and group and role:
            username_list = [u.strip() for u in usernames.split(",")]
            short_name_list = [s.strip() for s in short_names.split(",")]

            if len(username_list) != len(short_name_list):
                message = "The number of usernames and short names must match."
            else:
                for username, short_name in zip(username_list, short_name_list):
                    # Ensure user is added to the group
                    if group in user_group_mapping:
                        if any(u['username'] == username for u in user_group_mapping[group]):
                            message += f"User '{username}' is already in group '{group}'.\n"
                            continue
                        else:
                            user_group_mapping[group].append({"username": username, "short_name": short_name})
                    else:
                        user_group_mapping[group] = [{"username": username, "short_name": short_name}]

                    # Assign the role to the user in the namespace
                    user_role_mapping[username] = {"group": group, "role": role}
                    k8s_message = create_user_rolebinding(namespace=group, username=username, role_name=role)
                    message += f"User '{username}' (short name: '{short_name}') added to group '{group}' with role '{role}'. {k8s_message}\n"

                    # Create a service account for the user
                    sa_message = create_service_account(namespace=group, short_name=short_name, username=username)
                    message += f"{sa_message}\n"

    return render_template("add_users.html", message=message)

@app.route("/list_users")
def list_users_page():
    return render_template("list_users.html", user_groups=user_group_mapping, user_roles=user_role_mapping)

if __name__ == "__main__":
    app.run(debug=True)
