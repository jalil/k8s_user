<!DOCTYPE html>
<html>
<head>
    <title>Edit Users</title>
</head>
<body>
    <h1>Edit Users</h1>
    {% for group, users in user_groups.items() %}
        <h2>Group: {{ group }}</h2>
        <ul>
            {% for user in users %}
                <li>
                    {{ user.short_name }} ({{ user.username }}) 
                    <form method="POST" style="display:inline;">
                        <input type="hidden" name="username" value="{{ user.username }}">
                        <input type="hidden" name="short_name" value="{{ user.short_name }}">
                        <input type="hidden" name="old_group" value="{{ group }}">
                        <label>New Group:</label>
                        <input type="text" name="new_group" placeholder="New Group">
                        <label>New Role:</label>
                        <input type="text" name="new_role" placeholder="New Role">
                        <button type="submit" name="action" value="update">Update</button>
                        <button type="submit" name="action" value="delete">Delete</button>
                    </form>
                </li>
            {% endfor %}
        </ul>
    {% endfor %}
</body>
</html>
