import json
from datetime import datetime
from app.extensions import db


class AdminAuditLog(db.Model):
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # CREATE_PRODUCT, EDIT_PRODUCT, SOFT_DELETE_PRODUCT, RESTORE_PRODUCT, etc.
    entity_type = db.Column(db.String(100), nullable=False, index=True)  # Product, Order, Category, etc.
    entity_id = db.Column(db.String(100), nullable=True, index=True)
    details_json = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', back_populates='audit_logs')

    @classmethod
    def log_action(cls, user_id, action, entity_type, entity_id=None, details=None, ip_address=None):
        log = cls(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            details_json=details if isinstance(details, dict) else {'message': str(details)},
            ip_address=ip_address
        )
        db.session.add(log)
        return log

    def __repr__(self):
        return f'<AdminAuditLog user_id={self.user_id} action={self.action} entity={self.entity_type}#{self.entity_id}>'
