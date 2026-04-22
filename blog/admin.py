from django.contrib import admin
from .models import Post

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_published', 'published_at']
    list_filter = ['category', 'is_published']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'slug', 'excerpt', 'content', 'featured_image', 'category')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description')
        }),
        ('Publishing', {
            'fields': ('is_published', 'published_at', 'author_name', 'read_time')
        }),
    )