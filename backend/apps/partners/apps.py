from django.apps import AppConfig


class PartnersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.partners"
    label = "partners"
    verbose_name = "Partners & sales"

    def ready(self):
        from django.db.models.signals import pre_delete

        from .deletion import delete_agent_data
        from .models import AgentContract, AgentProfile

        # An agent takes the applications they filed, and the student accounts
        # left empty by that, with them. See deletion.py. The admin's proxy
        # views of an agent send their own signals, so each is connected.
        from django.apps import apps as registry

        def remove_agent_data(sender, instance, **kwargs):
            delete_agent_data(instance)

        for model in registry.get_models():
            if issubclass(model, AgentProfile):
                pre_delete.connect(
                    remove_agent_data,
                    sender=model,
                    weak=False,
                    dispatch_uid=f"delete-agent-data-{model._meta.label_lower}",
                )

        # The signed contract is a stored file like any other upload.
        from django.db.models.signals import post_delete

        def remove_contract_file(sender, instance, **kwargs):
            if instance.file and instance.file.name:
                instance.file.storage.delete(instance.file.name)

        post_delete.connect(
            remove_contract_file, sender=AgentContract, weak=False, dispatch_uid="delete-contract-file"
        )
