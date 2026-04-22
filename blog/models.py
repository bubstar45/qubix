from django.db import models
from django.urls import reverse
from django.utils import timezone

class Post(models.Model):
    CATEGORY_CHOICES = [
        ('beginner', 'Beginner Guides'),
        ('market', 'Market Analysis'),
        ('platform', 'Platform Updates'),
        ('comparison', 'Comparisons'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    excerpt = models.TextField(max_length=300)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='blog/', blank=True, null=True)
    
    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    # Publishing
    published_at = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(default=True)
    
    # Category
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='beginner')
    
    # Author
    author_name = models.CharField(max_length=100, default='Qubix Team')
    
    # Reading time
    read_time = models.IntegerField(default=5)
    
    class Meta:
        ordering = ['-published_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('blog_detail', args=[self.slug])