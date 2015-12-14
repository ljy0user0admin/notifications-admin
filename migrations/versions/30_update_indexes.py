"""empty message

Revision ID: 1691efaa342
Revises: 30_update_indexes.py
Create Date: 2015-12-09 13:15:00.773848

"""

# revision identifiers, used by Alembic.
revision = '30_update_indexes'
down_revision = '20_initialise_data'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'state',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.create_index(op.f('ix_users_email_address'), 'users', ['email_address'], unique=False)
    op.create_index(op.f('ix_users_name'), 'users', ['name'], unique=False)
    op.create_index(op.f('ix_users_role_id'), 'users', ['role_id'], unique=False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_users_role_id'), table_name='users')
    op.drop_index(op.f('ix_users_name'), table_name='users')
    op.drop_index(op.f('ix_users_email_address'), table_name='users')
    op.alter_column('users', 'state',
               existing_type=sa.VARCHAR(),
               nullable=True)
    ### end Alembic commands ###