from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

# User Schemas


class UserCreate(BaseModel):
    login: str
    password: str
    is_admin: bool


class UserLogin(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    login: str
    role: str


class UserUpdateLogin(BaseModel):
    login: str


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


class ClientCreate(BaseModel):
    name: str
    clientIp: str
    subnetId: UUID
    userId: UUID  


class ClientResponse(ClientBase):
    id: UUID
    isEnabled: bool


class ClientEnableDisable(BaseModel):
    clientId: UUID
    #! deleted userId


class ClientUpdateName(BaseModel):
    name: str


class ClientUpdateAddress(BaseModel):
    clientIp: str


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
    name: str


class SubnetUpdateSubnetIp(BaseModel):
    subnetIp: str


class SubnetUpdateSubnetMask(BaseModel):
    subnetMask: int


class SubnetDelete(BaseModel):
    subnetId: UUID
