from .base import LaxDTO

########################################################################################


class UpdateManyToManyQuery(LaxDTO):
    overwrite: bool


########################################################################################


class PatchManyToManyQuery(UpdateManyToManyQuery):
    overwrite: bool = False


########################################################################################


class PutManyToManyQuery(UpdateManyToManyQuery):
    overwrite: bool = True
