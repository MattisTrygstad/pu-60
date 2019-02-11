from django.contrib.auth.models import Group, User
from django.core import management

# flush db
management.call_command('flush', verbosity=0, interactive=False)
print("!----DB flushed----!")

# setup base data
g1 = Group.objects.create(name='students')
g2 = Group.objects.create(name='assistants')
g3 = Group.objects.create(name='course_coordinators')

u1 = User.objects.create_user(username='admin', password='123', is_staff=True, is_superuser=True)

print("Saving new data...")
for v in list(locals().values()):
    try:
        v.save()
    except (AttributeError, TypeError):
        pass
print("DB successfully reset!")
