from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from api.models import PublicDeepfakeArchive


class Command(BaseCommand):
    help = "Create moderator group with appropriate permissions"

    def handle(self, *args, **options):
        # Create moderator group
        moderator_group, created = Group.objects.get_or_create(name="PDA_Moderator")
        if created:
            self.stdout.write(self.style.SUCCESS("Successfully created PDA_Moderator group"))
        else:
            self.stdout.write(self.style.SUCCESS("PDA_Moderator group already exists"))

        # Get content type for PDA model
        pda_content_type = ContentType.objects.get_for_model(PublicDeepfakeArchive)

        # Get permissions
        view_pda = Permission.objects.get(
            content_type=pda_content_type, codename="view_publicdeepfakearchive"
        )
        change_pda = Permission.objects.get(
            content_type=pda_content_type, codename="change_publicdeepfakearchive"
        )
        delete_pda = Permission.objects.get(
            content_type=pda_content_type, codename="delete_publicdeepfakearchive"
        )

        # Assign permissions to moderator group
        moderator_group.permissions.clear()
        moderator_group.permissions.add(view_pda, change_pda, delete_pda)

        self.stdout.write(self.style.SUCCESS("Assigned permissions to PDA_Moderator group"))
