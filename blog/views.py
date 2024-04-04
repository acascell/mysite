from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView

from .forms import EmailPostForm, CommentForm, SearchForm
from .models import Post, Comment
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail
from django.views.decorators.http import require_POST

from taggit.models import Tag
from django.db.models import Count

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

# Create your views here.


class PostListView(ListView):
    queryset = Post.objects.all()
    context_object_name = "posts"
    paginate_by = 3
    template_name = "blog/post/list.html"


def post_list(request, tag_slug=None):
    post_get_list = Post.published.all()
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        post_get_list = post_get_list.filter(tags__in=[tag])
    # paginator with 3 post per page
    paginator = Paginator(post_get_list, 3)
    page_number = request.GET.get("page", 1)
    try:
        posts = paginator.get_page(page_number)
    except EmptyPage:
        # if page number is out of pages return the last page of results
        posts = paginator.page(paginator.num_pages)
    except PageNotAnInteger:
        posts = paginator.page(1)

    context = {"posts": posts, "tag": tag}
    return render(request, "blog/post/list.html", context)


def post_detail(request, year, month, day, post):
    post = get_object_or_404(
        Post,
        status=Post.Status.PUBLISHED,
        slug=post,
        publish__year=year,
        publish__month=month,
        publish__day=day,
    )
    comments = post.comments.filter(active=True)
    form = CommentForm()

    post_ids_tag = post.tags.values_list("id", flat=True)
    similar_post = Post.published.filter(tags__in=post_ids_tag).exclude(id=post.id)
    similar_post = similar_post.annotate(same_tags=Count("tags")).order_by(
        "-same_tags", "-publish"
    )[:4]
    context = {
        "post": post,
        "comments": comments,
        "form": form,
        "similar_post": similar_post,
    }
    return render(request, "blog/post/detail.html", context)


def post_share(request, post_id):
    post = get_object_or_404(Post, id=post_id, status=Post.Status.PUBLISHED)
    sent = False

    if request.method == "POST":
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends your read {post.title}"
            message = f"{post.title} at {post_url}\n\n"
            send_mail(subject, message, "infocascella@gmail.com", [cd["to"]])
            sent = True

    else:
        form = EmailPostForm()
    context = {"post": post, "form": form, "sent": sent}
    return render(request, "blog/post/share.html", context)


@require_POST
def post_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id, status=Post.Status.PUBLISHED)
    comment = None
    form = CommentForm(data=request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.save()
    context = {"post": post, "form": form, "comment": comment}
    return render(request, "blog/post/comment.html", context)


def post_search(request):
    form = SearchForm()
    query = None
    results = []

    if "query" in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data["query"]
            search_vector = SearchVector(
                "title", weight="A", config="spanish"
            ) + SearchVector("body", weight="B", config="spanish")
            search_query = SearchQuery(query, config="spanish")
            results = (
                Post.published.annotate(
                    search=search_vector, rank=SearchRank(search_vector, search_query)
                )
                .filter(rank__gte=0.3)
                .order_by("-rank")
            )

    context = {"form": form, "query": query, "results": results}

    return render(request, "blog/post/search.html", context)
