from django.contrib import admin

# Register your models here.
from .models import Category
from .models import Testimonial
admin.site.register(Testimonial)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_featured', 'created_at')
    list_filter = ('is_featured',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(Category, CategoryAdmin)
