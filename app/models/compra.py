from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


class Compra(Base):
    """Registro de compra para que el vendedor coordine el domicilio."""

    __tablename__ = "compras"

    id = Column(Integer, primary_key=True, index=True)
    comprador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    metodo_pago = Column(String(40), nullable=False, default="tarjeta_prueba")
    referencia_pago = Column(String(32), nullable=False, default="")
    estado = Column(String(40), nullable=False, default="pago_simulado_aprobado")
    creada_en = Column(DateTime, nullable=False, default=datetime.utcnow)

    comprador = relationship("Usuario", foreign_keys=[comprador_id], back_populates="compras")
    producto = relationship("Producto", back_populates="compras")
