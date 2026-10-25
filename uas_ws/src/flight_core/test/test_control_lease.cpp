#include <gtest/gtest.h>

#include "flight_core/control_lease.hpp"

using flight_core::ControlLease;

TEST(ControlLease, AcquireGrantsExclusiveLease)
{
  ControlLease lease;
  const auto first = lease.acquire("a");
  ASSERT_TRUE(first);
  EXPECT_TRUE(lease.is_holder(*first));
  EXPECT_EQ(lease.holder_name(), "a");
  EXPECT_FALSE(lease.acquire("b"));
}

TEST(ControlLease, ReleaseRequiresHolder)
{
  ControlLease lease;
  const auto id = lease.acquire("a");
  ASSERT_TRUE(id);
  EXPECT_FALSE(lease.release(*id + 1));
  EXPECT_TRUE(lease.held());
  EXPECT_TRUE(lease.release(*id));
  EXPECT_FALSE(lease.held());
  EXPECT_FALSE(lease.is_holder(*id));
}

TEST(ControlLease, ResetClearsAndIssuesNewId)
{
  ControlLease lease;
  const auto first = lease.acquire("a");
  ASSERT_TRUE(first);
  lease.reset();
  EXPECT_FALSE(lease.held());
  EXPECT_TRUE(lease.holder_name().empty());

  const auto second = lease.acquire("b");
  ASSERT_TRUE(second);
  EXPECT_NE(*first, *second);
  EXPECT_FALSE(lease.is_holder(*first));
}

TEST(ControlLease, ZeroIsNeverHolder)
{
  ControlLease lease;
  EXPECT_FALSE(lease.is_holder(0));
  ASSERT_TRUE(lease.acquire("a"));
  EXPECT_FALSE(lease.is_holder(0));
}
