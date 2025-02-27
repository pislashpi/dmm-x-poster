"""Initial migration

Revision ID: 3bec4ce06d17
Revises: 
Create Date: 2025-02-28 02:54:48.101103

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3bec4ce06d17'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dmm_product_id', sa.String(length=50), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('actresses', sa.Text(), nullable=True),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('package_image_url', sa.Text(), nullable=True),
    sa.Column('maker', sa.Text(), nullable=True),
    sa.Column('genres', sa.Text(), nullable=True),
    sa.Column('release_date', sa.Date(), nullable=True),
    sa.Column('fetched_at', sa.DateTime(), nullable=True),
    sa.Column('posted', sa.Boolean(), nullable=True),
    sa.Column('last_posted_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dmm_product_id')
    )
    op.create_table('images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('image_url', sa.Text(), nullable=False),
    sa.Column('local_path', sa.Text(), nullable=True),
    sa.Column('downloaded', sa.Boolean(), nullable=True),
    sa.Column('selected', sa.Boolean(), nullable=True),
    sa.Column('selection_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('post_text', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(), nullable=False),
    sa.Column('posted_at', sa.DateTime(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('post_images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('image_id', sa.Integer(), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('post_images')
    op.drop_table('posts')
    op.drop_table('images')
    op.drop_table('products')
    # ### end Alembic commands ###
