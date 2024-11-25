from flask import Flask, request, render_template
from kubernetes import client, config

app = Flask(__name__)

# Load Kubernetes configuration
config.load_kube_config()
v1 = client.CoreV1Api()
rbac_api = client.RbacAuthorizationV1Api()

user_group_mapping = {}
user_role_mapping = {}

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
        group = request.form.get("group")
        role = request.form.get("role")

        if usernames and group and role:
            username_list = [u.strip() for u in usernames.split(",")]
            for username in username_list:
                # Ensure user is added to the group
                if group in user_group_mapping:
                    if username not in user_group_mapping[group]:
                        user_group_mapping[group].append(username)
                else:
                    user_group_mapping[group] = [username]

                # Assign the role to the user in the namespace
                user_role_mapping[username] = {"group": group, "role": role}
                k8s_message = create_user_rolebinding(namespace=group, username=username, role_name=role)
                message += f"User '{username}' added to group '{group}' with role '{role}'. {k8s_message}\n"

    return render_template("add_users.html", message=message)

@app.route("/list_users")
def list_users_page():
    return render_template("list_users.html", user_groups=user_group_mapping, user_roles=user_role_mapping)

if __name__ == "__main__":
    app.run(debug=True)
