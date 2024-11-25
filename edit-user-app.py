from flask import Flask, request, render_template, redirect, url_for
from kubernetes import client, config

app = Flask(__name__)

# Load Kubernetes configuration
config.load_kube_config()
v1 = client.CoreV1Api()
rbac_api = client.RbacAuthorizationV1Api()

user_group_mapping = {}  # Group -> List of users (short name and username)
user_role_mapping = {}  # Username -> Role details

# Utility function to delete a service account
def delete_service_account(namespace, name):
    try:
        v1.delete_namespaced_service_account(name=name, namespace=namespace)
        return f"ServiceAccount '{name}' deleted successfully from namespace '{namespace}'."
    except client.exceptions.ApiException as e:
        return f"An error occurred while deleting the ServiceAccount: {e}"

# Utility function to delete a RoleBinding
def delete_rolebinding(namespace, username, role_name):
    rolebinding_name = f"{username}-{role_name}-binding"
    try:
        rbac_api.delete_namespaced_role_binding(name=rolebinding_name, namespace=namespace)
        return f"RoleBinding '{rolebinding_name}' deleted successfully."
    except client.exceptions.ApiException as e:
        return f"An error occurred while deleting the RoleBinding: {e}"

@app.route("/edit_users", methods=["GET", "POST"])
def edit_users():
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username")
        short_name = request.form.get("short_name")
        old_group = request.form.get("old_group")
        new_group = request.form.get("new_group")
        new_role = request.form.get("new_role")

        if action == "update":
            # Remove the user from the old group
            user_group_mapping[old_group] = [
                u for u in user_group_mapping[old_group] if u['username'] != username
            ]
            if not user_group_mapping[old_group]:
                del user_group_mapping[old_group]  # Delete group if empty

            # Add the user to the new group
            if new_group in user_group_mapping:
                user_group_mapping[new_group].append({"username": username, "short_name": short_name})
            else:
                user_group_mapping[new_group] = [{"username": username, "short_name": short_name}]

            # Update Kubernetes role binding
            delete_rolebinding(old_group, username, user_role_mapping[username]["role"])
            create_user_rolebinding(namespace=new_group, username=username, role_name=new_role)

            # Update service account
            delete_service_account(old_group, short_name)
            create_service_account(namespace=new_group, short_name=short_name, username=username)

            # Update user mapping
            user_role_mapping[username] = {"group": new_group, "role": new_role}

        elif action == "delete":
            # Delete Kubernetes resources
            delete_rolebinding(old_group, username, user_role_mapping[username]["role"])
            delete_service_account(old_group, short_name)

            # Remove the user from the group and mappings
            user_group_mapping[old_group] = [
                u for u in user_group_mapping[old_group] if u['username'] != username
            ]
            if not user_group_mapping[old_group]:
                del user_group_mapping[old_group]  # Delete group if empty
            del user_role_mapping[username]

    return render_template("edit_users.html", user_groups=user_group_mapping, user_roles=user_role_mapping)

@app.route("/list_users")
def list_users_page():
    return render_template("list_users.html", user_groups=user_group_mapping, user_roles=user_role_mapping)

if __name__ == "__main__":
    app.run(debug=True)
