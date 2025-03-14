from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

# User Schemas
class UserBase(BaseModel):
    login: str
    clientId: int

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID
    role: str

class UserUpdateLogin(BaseModel):
    userId: UUID
    login: str

class UserUpdateClientId(BaseModel):
    userId: UUID
    clientId: int

class UserChangePassword(BaseModel):
    userId: UUID
    oldPassword: str
    newPassword: str

class UserDelete(BaseModel):
    userId: UUID

# Client Schemas
class ClientBase(BaseModel):
    name: str
    clientIp: str
    publicKey: str
    privateKeyRef: str
    subnetId: UUID

class ClientCreate(ClientBase):
    pass

class ClientResponse(ClientBase):
    id: UUID
    isEnabled: bool

class ClientEnableDisable(BaseModel):
    userId: UUID
    clientId: UUID

class ClientUpdateName(BaseModel):
    userId: UUID
    name: str

class ClientUpdateAddress(BaseModel):
    userId: UUID
    clientIp: str

class ClientDelete(BaseModel):
    clientId: UUID

class ClientQRCodeResponse(BaseModel):
    qrcode: str

class ClientConfigurationResponse(BaseModel):
    configuration: str

# Subnet Schemas
class SubnetBase(BaseModel):
    name: str
    subnetIp: str
    subnetMask: int

class SubnetCreate(SubnetBase):
    userId: UUID

class SubnetResponse(SubnetBase):
    id: UUID

class SubnetUpdateName(BaseModel):
    userId: UUID
    name: str

class SubnetUpdateSubnetIp(BaseModel):
    userId: UUID
    subnetIp: str

class SubnetUpdateSubnetMask(BaseModel):
    userId: UUID
    subnetMask: int

class SubnetDelete(BaseModel):
    subnetId: UUID
