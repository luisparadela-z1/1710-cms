# core/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import reverse
from .models import Blog, Post, Tag
from .serializers import (
    UserSerializer, BlogSerializer, PostSerializer, 
    PostCreateSerializer, TagSerializer, UserRegistrationSerializer, UserLoginSerializer
)
from .permissions import IsOwnerOrSuperuser, IsOwnerOrSuperuserForBlog, IsSuperuserOrReadOnly

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for user management with registration and login endpoints.
    Only superusers can see all users, regular users can only see themselves.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperuserOrReadOnly]
    
    def get_queryset(self):
        # Superusers can see all users, regular users only see themselves
        if self.request.user.is_superuser:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """
        Register new users with automatic blog creation.
        """
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Automatically create blog for new user
            Blog.objects.create(
                user=user,
                title=f"Blog de {user.username}"
            )
            # Create token for user
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key,
                'message': 'User registered successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """
        User login with token generation.
        """
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key,
                'message': 'Login successful'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BlogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for blog management with owner-based permissions.
    """
    serializer_class = BlogSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrSuperuserForBlog]
    
    def get_queryset(self):
        # Superusers can see all blogs, others only their own
        if self.request.user.is_superuser:
            return Blog.objects.all()
        return Blog.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Automatically assign user to blog
        serializer.save(user=self.request.user)

class TagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tag management.
    Any authenticated user can create tags, but only superusers can modify/delete.
    """
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperuserOrReadOnly]

class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for post management with custom permissions and actions.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrSuperuser]
    
    def get_queryset(self):
        # Any authenticated user can see all posts
        return Post.objects.all()
    
    def get_serializer_class(self):
        # Use different serializer for create/update operations
        if self.action in ['create', 'update', 'partial_update']:
            return PostCreateSerializer
        return PostSerializer
    
    def perform_create(self, serializer):
        # Automatically assign user's blog to post
        user_blog = Blog.objects.filter(user=self.request.user).first()
        if user_blog:
            serializer.save(blog=user_blog)
        else:
            # Create blog automatically if it doesn't exist
            blog = Blog.objects.create(
                user=self.request.user,
                title=f"Blog de {self.request.user.username}"
            )
            serializer.save(blog=blog)
    
    @action(detail=False, methods=['get'])
    def published(self, request):
        """
        Endpoint to get only published posts.
        """
        posts = self.get_queryset().filter(is_published=True)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_tag(self, request):
        """
        Endpoint to filter posts by tag name.
        """
        tag_name = request.query_params.get('tag', None)
        if tag_name:
            posts = self.get_queryset().filter(tags__name__icontains=tag_name)
        else:
            posts = self.get_queryset()
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

@api_view(['GET'])
def api_root(request):
    """
    API Root view that shows all available endpoints.
    """
    return Response({
        'users': request.build_absolute_uri(reverse('user-list')),
        'blogs': request.build_absolute_uri(reverse('blog-list')),
        'posts': request.build_absolute_uri(reverse('post-list')),
        'tags': request.build_absolute_uri(reverse('tag-list')),
    })