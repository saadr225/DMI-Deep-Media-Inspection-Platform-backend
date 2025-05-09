from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0025_forumlike_like_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='forumlike',
            name='like_type',
            field=models.CharField(choices=[('like', 'Like'), ('dislike', 'Dislike')], default='like', max_length=10),
        ),
    ] 