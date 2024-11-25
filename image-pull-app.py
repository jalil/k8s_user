from flask import Flask, request, render_template, redirect, url_for
from kubernetes import client, config

app = Flask(__name__)

# Load Kubernetes configuration
config.load_kube_config()
v1 = client.CoreV1Api()
rbac_api = client.RbacAuthorizationV1Api()

user_group_mapping = {}

# Utility function to create a namespace (group)
def create_namespace(name):
    try:
        v1.read_namespace(name)
        return f"Namespace '{name}' already exists.", False
    except client.exceptions.ApiException as e:
        if e.status == 404:
            namespace = client.V1Namespace(
                metadata=client.V1ObjectMeta(name=name)
            )
            try:
                v1.create_namespace(namespace)
                return f"Namespace '{name}' created successfully.", True
            except client.exceptions.ApiException as e:
                return f"An error occurred: {e}", False
        else:
            return f"An error occurred: {e}", False

# Utility function to create a ServiceAccount with an imagePullSecret
def create_service_account(namespace, shortname, username):
    service_account_name = shortname
    service_account = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=service_account_name,
            labels={"hpc/long-account": username}
        ),
        image_pull_secrets=[client.V1LocalObjectReference(name="gcr-cred")]
    )
    try:
        v1.create_namespaced_service_account(namespace, service_account)
        return f"ServiceAccount '{service_account_name}' created with imagePullSecret 'gcr-cred' in namespace '{namespace}'."
    except client.exceptions.ApiException as e:
        return f"An error occurred while creating ServiceAccount: {e}"

# Utility function to create a RoleBinding for a group in a namespace
def create_rolebinding(namespace: str, group: str, role_name="admin"):
    role_ref = client.V1RoleRef(
        api_group="rbac.authorization.k8s.io",
        kind="Role",
        name=role_name
    )

    subject = client.V1Subject(
        kind="Group",
        name=group,
        api_group="rbac.authorization.k8s.io"
    )

    role_binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(name=f"{group}-rolebinding", namespace=namespace),
        role_ref=role_ref,
        subjects=[subject]
    )

    try:
        rbac_api.create_namespaced_role_binding(namespace=namespace, body=role_binding)
        return f"RoleBinding '{group}-rolebinding' created in namespace '{namespace}'."
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
                rolebinding_message = create_rolebinding(namespace=group_name, group=group_name)
                message += f" {rolebinding_message}"
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

@app.route("/add_user", methods=["GET", "POST"])
def add_user():
    message = ""
    if request.method == "POST":
        group = request.form.get("group")
        users = request.form.get("users")  # Expecting "username:shortname, username2:shortname2"
        if group and users:
            users = [user.strip() for user in users.split(",")]
            for user in users:
                if ":" in user:
                    username, shortname = user.split(":")
                    if group not in user_group_mapping:
                        user_group_mapping[group] = []
                    if username not in [u["username"] for u in user_group_mapping[group]]:
                        user_group_mapping[group].append({"username": username, "shortname": shortname})
                        service_account_message = create_service_account(group, shortname, username)
                        message += f"User '{username}' added to group '{group}'. {service_account_message}<br>"
                    else:
                        message += f"User '{username}' already exists in group '{group}'.<br>"
                else:
                    message += f"Invalid format for user '{user}'. Use 'username:shortname'.<br>"
    return render_template("add_user.html", message=message)

@app.route("/list_users")
def list_users_page():
    return render_template("list_users.html", user_groups=user_group_mapping)

if __name__ == "__main__":
    app.run(debug=True)
